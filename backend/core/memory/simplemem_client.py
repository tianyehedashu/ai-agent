"""
SimpleMem Adapter - 直接集成 SimpleMem 核心功能

基于 SimpleMem 论文实现的本地适配器，无需 MCP 服务。
直接复用现有的 LongTermMemoryStore 和 LLM Gateway。

SimpleMem 核心策略：
1. 语义结构化压缩 - 滑动窗口 + 信息密度过滤
2. 递归记忆整合 - 周期性合并相似记忆
3. 自适应查询检索 - 根据查询复杂度动态调整 Top-K

官方仓库: https://github.com/aiming-lab/SimpleMem
论文: https://arxiv.org/abs/2601.02553

使用方法:
```python
adapter = SimpleMemAdapter(llm_gateway, memory_store)
await adapter.process_and_store(messages, user_id, session_id)
results = await adapter.adaptive_retrieve(user_id, query)
```
"""

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import re
from typing import TYPE_CHECKING, Any

from rank_bm25 import BM25Okapi

from core.types import Message, MessageRole
from utils.logging import get_logger
from utils.tokens import count_tokens

if TYPE_CHECKING:
    from core.llm.gateway import LLMGateway
    from core.memory.langgraph_store import LongTermMemoryStore

logger = get_logger(__name__)


@dataclass
class SimpleMemConfig:
    """SimpleMem 配置"""

    # 滑动窗口
    window_size: int = 10
    window_stride: int = 5  # 步长（重叠）

    # 信息密度过滤
    novelty_threshold: float = 0.35
    min_content_length: int = 20

    # 自适应检索
    k_min: int = 3  # 简单查询
    k_max: int = 15  # 复杂查询
    complexity_threshold: float = 0.5

    # 合并
    consolidation_interval: int = 50  # 每 N 条记忆触发合并

    # 提取模型（使用小模型节省成本，None 则使用默认模型）
    # 推荐：gpt-4o-mini, deepseek-chat, claude-3-haiku
    extraction_model: str | None = None


@dataclass
class MemoryAtom:
    """原子记忆单元（SimpleMem 核心概念）"""

    id: str
    content: str
    entities: list[str]
    timestamp: datetime
    source_session: str
    importance: float = 5.0
    tokens: int = 0


class SimpleMemAdapter:
    """
    SimpleMem 本地适配器

    直接集成到现有架构，无需额外服务：
    - 使用 LongTermMemoryStore 存储
    - 使用 LLMGateway 做提取和摘要
    - 使用 BM25 做词法检索
    """

    def __init__(
        self,
        llm_gateway: "LLMGateway",
        memory_store: "LongTermMemoryStore",
        config: SimpleMemConfig | None = None,
    ) -> None:
        self.llm = llm_gateway
        self.store = memory_store
        self.config = config or SimpleMemConfig()

        # BM25 索引缓存
        self._bm25_corpus: dict[str, list[str]] = {}  # user_id -> documents
        self._bm25_index: dict[str, BM25Okapi] = {}  # user_id -> index

        # 记忆计数（用于触发合并）
        self._memory_count: dict[str, int] = {}

        logger.info("SimpleMemAdapter initialized")

    async def process_and_store(
        self,
        messages: list[Message],
        user_id: str,
        session_id: str,
    ) -> list[MemoryAtom]:
        """
        处理对话并存储记忆（SimpleMem Stage 1）

        Args:
            messages: 对话消息列表
            user_id: 用户 ID
            session_id: 会话 ID

        Returns:
            提取的原子记忆列表
        """
        if not messages:
            return []

        extracted: list[MemoryAtom] = []

        # 滑动窗口处理
        for i in range(0, len(messages), self.config.window_stride):
            window = messages[i : i + self.config.window_size]
            if not window:
                continue

            # 计算信息密度
            novelty = self._calculate_novelty(window)
            if novelty < self.config.novelty_threshold:
                logger.debug("Skipping low-novelty window at %d (%.2f)", i, novelty)
                continue

            # 提取原子记忆
            atom = await self._extract_atom(window, user_id, session_id)
            if atom:
                # 存储到 LongTermMemoryStore
                # 记忆按 session_id 隔离，实现"会话内长程记忆"
                # 注意：ChromaDB metadata 只支持 str/int/float/bool/None，
                # 所以需要将 entities 列表转换为 JSON 字符串
                await self.store.put(
                    session_id=session_id,  # 记忆按会话隔离
                    memory_type="simplemem_atom",
                    content=atom.content,
                    importance=atom.importance,
                    metadata={
                        "atom_id": atom.id,
                        "entities": json.dumps(atom.entities, ensure_ascii=False),
                        "user_id": user_id,  # 保留 user_id 用于审计
                        "timestamp": atom.timestamp.isoformat(),
                    },
                )
                extracted.append(atom)

                # 更新 BM25 索引（按 session_id 隔离）
                self._update_bm25_index(session_id, atom.content)

                # 检查是否需要合并
                self._memory_count[session_id] = self._memory_count.get(session_id, 0) + 1
                if self._memory_count[session_id] >= self.config.consolidation_interval:
                    await self._consolidate(session_id)

        logger.info(
            "Processed %d messages for session %s, extracted %d atoms",
            len(messages),
            session_id,
            len(extracted),
        )
        return extracted

    async def adaptive_retrieve(
        self,
        session_id: str,
        query: str,
        k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        自适应检索（SimpleMem Stage 3）

        根据查询复杂度动态调整检索深度，
        结合语义检索和词法检索。
        记忆按 session_id 隔离，只检索当前会话的记忆。

        Args:
            session_id: 会话 ID（记忆按会话隔离）
            query: 查询内容
            k: 检索数量（None 则自适应）

        Returns:
            检索到的记忆列表
        """
        # 1. 评估查询复杂度
        complexity = self._estimate_complexity(query)

        # 2. 动态确定 k
        if k is None:
            if complexity < self.config.complexity_threshold:
                k = self.config.k_min
            else:
                ratio = (complexity - self.config.complexity_threshold) / (
                    1 - self.config.complexity_threshold
                )
                k = int(self.config.k_min + ratio * (self.config.k_max - self.config.k_min))

        logger.debug("Query complexity: %.2f, k=%d", complexity, k)

        # 3. 语义检索（通过 LongTermMemoryStore，按 session_id 隔离）
        semantic_results = await self.store.search(
            session_id=session_id,
            query=query,
            limit=k,
            memory_type="simplemem_atom",
        )

        # 4. BM25 词法检索（按 session_id 隔离）
        bm25_results = self._bm25_search(session_id, query, k)

        # 5. 合并去重（RRF 融合）
        merged = self._reciprocal_rank_fusion(semantic_results, bm25_results, k)

        return merged

    def _calculate_novelty(self, window: list[Message]) -> float:
        """计算窗口的信息新颖性"""
        content = " ".join(m.content or "" for m in window)
        if len(content) < self.config.min_content_length:
            return 0.0

        words = content.lower().split()
        unique_ratio = len(set(words)) / max(1, len(words))

        # 实体检测
        entities = re.findall(r"\b[A-Z][a-z]+\b|\b\d+[年月日天小时分钟秒]", content)
        entity_score = min(1.0, len(set(entities)) / 10)

        return unique_ratio * 0.4 + entity_score * 0.6

    async def _extract_atom(
        self,
        window: list[Message],
        user_id: str,
        session_id: str,
    ) -> MemoryAtom | None:
        """从窗口提取原子记忆"""
        content_parts = []
        for msg in window:
            role = msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role)
            content_parts.append(f"{role}: {msg.content or ''}")

        full_content = "\n".join(content_parts)
        if len(full_content) < self.config.min_content_length:
            return None

        # 使用 LLM 提取关键信息（可配置使用小模型节省成本）
        try:
            response = await self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": """提取对话的关键信息，返回 JSON：
{"summary": "一句话总结", "entities": ["实体1", "实体2"], "importance": 5}
importance: 1-10，10 最重要""",
                    },
                    {"role": "user", "content": full_content[:2000]},
                ],
                model=self.config.extraction_model,  # 使用专用小模型，None 则用默认
                max_tokens=200,
                temperature=0.1,
            )

            # 解析
            text = response.content or ""
            match = re.search(r"\{[^}]+\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                summary = data.get("summary", full_content[:150])
                entities = data.get("entities", [])[:10]
                importance = float(data.get("importance", 5))
            else:
                summary = full_content[:150]
                entities = []
                importance = 5.0

            atom_id = hashlib.md5(f"{session_id}:{summary[:50]}".encode()).hexdigest()[:12]

            return MemoryAtom(
                id=atom_id,
                content=summary,
                entities=entities,
                timestamp=datetime.now(UTC),
                source_session=session_id,
                importance=importance,
                tokens=count_tokens(summary),
            )

        except Exception as e:
            logger.warning("Failed to extract atom: %s", e)
            return None

    def _estimate_complexity(self, query: str) -> float:
        """估算查询复杂度"""
        score = 0.0

        words = query.split()
        if len(words) > 15:
            score += 0.3
        elif len(words) > 8:
            score += 0.15

        # 实体
        entities = re.findall(r"\b[A-Z][a-z]+\b", query)
        score += min(0.3, len(entities) * 0.1)

        # 时间
        if re.search(r"(昨天|今天|明天|上周|上个月|\d+天前|\d+月)", query):
            score += 0.2

        # 逻辑词
        if any(
            w in query.lower() for w in ["为什么", "怎么", "如何", "why", "how", "并且", "或者"]
        ):
            score += 0.15

        return min(1.0, score)

    def _update_bm25_index(self, session_id: str, content: str) -> None:
        """更新 BM25 索引（按 session_id 隔离）"""
        if session_id not in self._bm25_corpus:
            self._bm25_corpus[session_id] = []

        self._bm25_corpus[session_id].append(content)

        # 重建索引
        tokenized = [doc.split() for doc in self._bm25_corpus[session_id]]
        self._bm25_index[session_id] = BM25Okapi(tokenized)

    def _bm25_search(self, session_id: str, query: str, k: int) -> list[dict[str, Any]]:
        """BM25 词法检索（按 session_id 隔离）"""
        if session_id not in self._bm25_index:
            return []

        tokenized_query = query.split()
        scores = self._bm25_index[session_id].get_scores(tokenized_query)

        # 获取 top-k
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:k]:
            if score > 0:
                results.append(
                    {
                        "content": self._bm25_corpus[session_id][idx],
                        "bm25_score": float(score),
                        "source": "bm25",
                    }
                )
        return results

    def _reciprocal_rank_fusion(
        self,
        semantic: list[dict[str, Any]],
        lexical: list[dict[str, Any]],
        k: int,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """RRF 融合两种检索结果"""
        scores: dict[str, float] = {}
        docs: dict[str, dict[str, Any]] = {}

        # 语义结果
        for rank, doc in enumerate(semantic):
            content = doc.get("content", "")
            scores[content] = scores.get(content, 0) + 1 / (rrf_k + rank + 1)
            docs[content] = doc

        # 词法结果
        for rank, doc in enumerate(lexical):
            content = doc.get("content", "")
            scores[content] = scores.get(content, 0) + 1 / (rrf_k + rank + 1)
            if content not in docs:
                docs[content] = doc

        # 排序
        sorted_contents = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        return [docs[c] for c in sorted_contents[:k]]

    async def _consolidate(self, session_id: str) -> None:
        """合并相似记忆（SimpleMem Stage 2）"""
        logger.info("Triggering memory consolidation for session %s", session_id)
        self._memory_count[session_id] = 0
        # 实际合并逻辑可以后续实现
        # 这里简化处理，仅重置计数器


# 全局适配器实例
_simplemem_adapter: SimpleMemAdapter | None = None


def get_simplemem_adapter(
    llm_gateway: "LLMGateway",
    memory_store: "LongTermMemoryStore",
) -> SimpleMemAdapter:
    """获取 SimpleMem 适配器单例"""
    global _simplemem_adapter
    if _simplemem_adapter is None:
        _simplemem_adapter = SimpleMemAdapter(llm_gateway, memory_store)
    return _simplemem_adapter


def reset_simplemem_adapter() -> None:
    """重置适配器"""
    global _simplemem_adapter
    _simplemem_adapter = None
