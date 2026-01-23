"""
Tiered Memory Manager - 分层记忆管理器

实现工作记忆、短期记忆、长期记忆的分层管理。

记忆分层架构：
┌──────────────────┐
│   工作记忆        │  ← 当前会话上下文，生命周期：单次对话
│  (Working Memory) │    存储：内存
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   短期记忆        │  ← 会话历史，生命周期：24小时 - 7天
│  (Short-term)    │    存储：Redis/PostgreSQL（Checkpointer）
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   长期记忆        │  ← 用户偏好、事实，生命周期：永久
│  (Long-term)     │    存储：向量数据库 + PostgreSQL
└──────────────────┘

这是 2026 年主流的 Agent Token 优化策略之一。
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
import uuid

from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.runtime.infrastructure.engine.langgraph_checkpointer import LangGraphCheckpointer
    from domains.runtime.infrastructure.memory.langgraph_store import LongTermMemoryStore

logger = get_logger(__name__)


class MemoryTier(Enum):
    """记忆层级"""

    WORKING = "working"  # 工作记忆（当前上下文）
    SHORT_TERM = "short"  # 短期记忆（会话历史）
    LONG_TERM = "long"  # 长期记忆（永久存储）


class MemoryType(Enum):
    """记忆类型"""

    # 工作记忆类型
    CURRENT_TASK = "current_task"  # 当前任务
    TOOL_RESULTS = "tool_results"  # 工具结果
    INTERMEDIATE = "intermediate"  # 中间结果

    # 短期记忆类型
    SESSION_CONTEXT = "session_context"  # 会话上下文
    RECENT_DECISIONS = "recent_decisions"  # 近期决策

    # 长期记忆类型
    USER_PREFERENCE = "preference"  # 用户偏好
    FACTUAL_KNOWLEDGE = "fact"  # 事实知识
    PROCEDURE = "procedure"  # 操作步骤
    SESSION_SUMMARY = "session_summary"  # 会话摘要
    TODO = "todo"  # 待办事项


@dataclass
class MemoryItem:
    """记忆项"""

    id: str
    tier: MemoryTier
    type: MemoryType
    content: str
    importance: float = 5.0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0  # 与当前查询的相关性分数

    @classmethod
    def create(
        cls,
        tier: MemoryTier,
        type: MemoryType,
        content: str,
        importance: float = 5.0,
        metadata: dict[str, Any] | None = None,
    ) -> "MemoryItem":
        """创建记忆项的工厂方法"""
        return cls(
            id=str(uuid.uuid4()),
            tier=tier,
            type=type,
            content=content,
            importance=importance,
            metadata=metadata or {},
        )


@dataclass
class TieredMemoryConfig:
    """分层记忆配置"""

    # 短期记忆 TTL（小时）
    short_term_ttl_hours: int = 24

    # 长期记忆重要性阈值（低于此值不存储）
    long_term_importance_threshold: float = 6.0

    # 召回时各层级权重
    recall_weights: dict[MemoryTier, float] = field(
        default_factory=lambda: {
            MemoryTier.WORKING: 1.0,
            MemoryTier.SHORT_TERM: 0.8,
            MemoryTier.LONG_TERM: 0.6,
        }
    )

    # 各层级最大召回数量
    recall_limits: dict[MemoryTier, int] = field(
        default_factory=lambda: {
            MemoryTier.WORKING: 10,
            MemoryTier.SHORT_TERM: 5,
            MemoryTier.LONG_TERM: 5,
        }
    )

    # 工作记忆最大容量
    working_memory_max_items: int = 50


@dataclass
class RecallResult:
    """召回结果"""

    memories: list[MemoryItem]
    tier_counts: dict[MemoryTier, int]
    total_recalled: int

    @classmethod
    def empty(cls) -> "RecallResult":
        """创建空结果"""
        return cls(
            memories=[],
            tier_counts=dict.fromkeys(MemoryTier, 0),
            total_recalled=0,
        )


class TieredMemoryManager:
    """
    分层记忆管理器

    协调工作记忆、短期记忆、长期记忆的存取。

    设计原则：
    1. 工作记忆优先（最相关）
    2. 按重要性和相关性排序
    3. 自动记忆提升机制
    """

    def __init__(
        self,
        long_term_store: "LongTermMemoryStore",
        checkpointer: "LangGraphCheckpointer | None" = None,
        config: TieredMemoryConfig | None = None,
    ) -> None:
        """
        初始化分层记忆管理器

        Args:
            long_term_store: 长期记忆存储
            checkpointer: LangGraph 检查点管理器（用于短期记忆）
            config: 配置
        """
        self.long_term_store = long_term_store
        self.checkpointer = checkpointer
        self.config = config or TieredMemoryConfig()

        # 工作记忆（内存中，按 session_id 隔离）
        self._working_memory: dict[str, list[MemoryItem]] = {}

    async def recall(
        self,
        user_id: str,
        session_id: str,
        query: str,
        tiers: list[MemoryTier] | None = None,
        limit: int = 10,
    ) -> RecallResult:
        """
        召回记忆

        从指定层级中检索相关记忆，按相关性和重要性排序。

        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            query: 查询文本
            tiers: 要搜索的层级（默认所有）
            limit: 返回数量

        Returns:
            召回结果
        """
        tiers = tiers or list(MemoryTier)
        all_memories: list[tuple[MemoryItem, float]] = []
        tier_counts: dict[MemoryTier, int] = dict.fromkeys(MemoryTier, 0)

        for tier in tiers:
            tier_limit = self.config.recall_limits.get(tier, 5)
            tier_memories = await self._recall_from_tier(
                tier=tier,
                user_id=user_id,
                session_id=session_id,
                query=query,
                limit=tier_limit,
            )

            # 应用层级权重
            weight = self.config.recall_weights.get(tier, 0.5)
            for memory, score in tier_memories:
                weighted_score = score * weight
                memory.relevance_score = weighted_score
                all_memories.append((memory, weighted_score))
                tier_counts[tier] += 1

        # 按加权分数排序
        all_memories.sort(key=lambda x: x[1], reverse=True)

        # 取前 N 条
        final_memories = [m for m, _ in all_memories[:limit]]

        return RecallResult(
            memories=final_memories,
            tier_counts=tier_counts,
            total_recalled=len(final_memories),
        )

    async def _recall_from_tier(
        self,
        tier: MemoryTier,
        user_id: str,
        session_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[MemoryItem, float]]:
        """从特定层级召回"""
        if tier == MemoryTier.WORKING:
            return self._recall_working_memory(session_id, query, limit)
        elif tier == MemoryTier.SHORT_TERM:
            return await self._recall_short_term(session_id, query, limit)
        elif tier == MemoryTier.LONG_TERM:
            return await self._recall_long_term(user_id, query, limit)
        return []

    def _recall_working_memory(
        self,
        session_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[MemoryItem, float]]:
        """
        召回工作记忆

        使用简单的关键词匹配（工作记忆较小，不需要向量搜索）
        """
        memories = self._working_memory.get(session_id, [])
        results: list[tuple[MemoryItem, float]] = []
        query_lower = query.lower()

        for memory in memories:
            # 简单的关键词匹配计算相关性
            content_lower = memory.content.lower()
            if query_lower in content_lower:
                # 完全匹配得分更高
                score = 1.0
            elif any(word in content_lower for word in query_lower.split()):
                # 部分词匹配
                matching_words = sum(1 for word in query_lower.split() if word in content_lower)
                total_words = len(query_lower.split())
                score = matching_words / total_words if total_words > 0 else 0.5
            else:
                # 无匹配，但仍考虑重要性
                score = memory.importance / 20.0  # 基于重要性的基础分

            results.append((memory, score))

        # 按分数排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    async def _recall_short_term(
        self,
        session_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[MemoryItem, float]]:
        """
        召回短期记忆

        从 checkpointer 获取会话历史
        """
        # TODO: 实现从 checkpointer 获取会话历史
        # 目前 LangGraph checkpointer 主要用于状态持久化，
        # 不直接支持语义搜索，所以暂时返回空
        return []

    async def _recall_long_term(
        self,
        user_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[MemoryItem, float]]:
        """
        召回长期记忆

        使用向量搜索
        """
        try:
            results = await self.long_term_store.search(
                user_id=user_id,
                query=query,
                limit=limit,
            )

            memories = []
            for r in results:
                # 安全获取 memory_type，默认为 "fact"
                memory_type_str = r.get("type", "fact")
                try:
                    memory_type = MemoryType(memory_type_str)
                except ValueError:
                    memory_type = MemoryType.FACTUAL_KNOWLEDGE

                memory = MemoryItem(
                    id=r["id"],
                    tier=MemoryTier.LONG_TERM,
                    type=memory_type,
                    content=r["content"],
                    importance=r.get("importance", 5.0),
                    metadata=r.get("metadata", {}),
                )
                score = r.get("score", 0.5)
                memories.append((memory, score))

            return memories
        except Exception as e:
            logger.error("Failed to recall long-term memory: %s", e, exc_info=True)
            return []

    async def store(
        self,
        user_id: str,
        session_id: str,
        memory: MemoryItem,
    ) -> str:
        """
        存储记忆

        根据记忆层级决定存储位置。

        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            memory: 记忆项

        Returns:
            记忆 ID
        """
        if memory.tier == MemoryTier.WORKING:
            return self._store_working_memory(session_id, memory)
        elif memory.tier == MemoryTier.LONG_TERM:
            return await self._store_long_term(user_id, memory)
        # 短期记忆通过 checkpointer 自动管理
        return memory.id

    def _store_working_memory(
        self,
        session_id: str,
        memory: MemoryItem,
    ) -> str:
        """存储工作记忆"""
        if session_id not in self._working_memory:
            self._working_memory[session_id] = []

        # 检查容量限制
        max_items = self.config.working_memory_max_items
        if len(self._working_memory[session_id]) >= max_items:
            # 移除最不重要的记忆
            self._working_memory[session_id].sort(key=lambda m: m.importance, reverse=True)
            self._working_memory[session_id] = self._working_memory[session_id][: max_items - 1]

        self._working_memory[session_id].append(memory)
        logger.debug(
            "Stored working memory: %s (session=%s, type=%s)",
            memory.id[:8],
            session_id[:8],
            memory.type.value,
        )
        return memory.id

    async def _store_long_term(
        self,
        user_id: str,
        memory: MemoryItem,
    ) -> str:
        """存储长期记忆"""
        # 检查重要性阈值
        if memory.importance < self.config.long_term_importance_threshold:
            logger.debug(
                "Memory importance %.1f below threshold %.1f, skipping long-term storage",
                memory.importance,
                self.config.long_term_importance_threshold,
            )
            return memory.id

        try:
            memory_id = await self.long_term_store.put(
                user_id=user_id,
                memory_type=memory.type.value,
                content=memory.content,
                importance=memory.importance,
                metadata=memory.metadata,
            )
            logger.info(
                "Stored long-term memory: %s (user=%s, type=%s, importance=%.1f)",
                memory_id[:8],
                user_id[:8] if len(user_id) >= 8 else user_id,
                memory.type.value,
                memory.importance,
            )
            return memory_id
        except Exception as e:
            logger.error("Failed to store long-term memory: %s", e, exc_info=True)
            return memory.id

    def clear_working_memory(self, session_id: str) -> int:
        """
        清空工作记忆

        Args:
            session_id: 会话 ID

        Returns:
            清除的记忆数量
        """
        if session_id in self._working_memory:
            count = len(self._working_memory[session_id])
            del self._working_memory[session_id]
            logger.info("Cleared %d working memories for session %s", count, session_id[:8])
            return count
        return 0

    async def promote_to_long_term(
        self,
        user_id: str,
        session_id: str,
        memory_id: str,
    ) -> str | None:
        """
        将工作记忆提升为长期记忆

        当某条工作记忆被反复引用或标记为重要时，可以提升为长期记忆。

        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            memory_id: 记忆 ID

        Returns:
            新的长期记忆 ID，或 None（如果提升失败）
        """
        if session_id not in self._working_memory:
            return None

        for i, memory in enumerate(self._working_memory[session_id]):
            if memory.id == memory_id:
                # 找到目标记忆
                memory.tier = MemoryTier.LONG_TERM
                # 提升重要性
                memory.importance = max(
                    memory.importance,
                    self.config.long_term_importance_threshold,
                )
                # 存储到长期记忆
                new_id = await self._store_long_term(user_id, memory)
                # 从工作记忆中移除
                self._working_memory[session_id].pop(i)
                logger.info(
                    "Promoted working memory %s to long-term memory %s",
                    memory_id[:8],
                    new_id[:8],
                )
                return new_id

        return None

    def get_working_memory_stats(self, session_id: str) -> dict[str, Any]:
        """
        获取工作记忆统计

        Args:
            session_id: 会话 ID

        Returns:
            统计信息
        """
        memories = self._working_memory.get(session_id, [])
        type_counts: dict[str, int] = {}
        for m in memories:
            type_counts[m.type.value] = type_counts.get(m.type.value, 0) + 1

        return {
            "total_count": len(memories),
            "type_counts": type_counts,
            "avg_importance": (sum(m.importance for m in memories) / len(memories))
            if memories
            else 0,
            "max_capacity": self.config.working_memory_max_items,
            "capacity_used": len(memories) / self.config.working_memory_max_items,
        }
