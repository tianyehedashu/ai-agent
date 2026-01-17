# AI Agent Token 优化策略文档

> 文档版本：v1.0
> 更新日期：2026-01-16
> 适用范围：AI-Agent 后端系统

## 1. 概述

本文档分析当前系统对主流 Token 优化方案的实现情况，并提供详细的优化建议和实施方案。

### 1.1 2026 年主流 Agent Token 优化策略

| 策略 | 说明 | 成本节省 | 当前系统状态 |
|------|------|----------|--------------|
| 提示词缓存 (Prompt Caching) | 缓存系统提示词和早期记忆 | 50%-90% | ❌ 未实现 |
| 滑动窗口 (Sliding Window) | 只保留最近 N 条对话 | 30%-60% | ✅ 已实现 |
| 记忆总结 (Summarization) | 定期对长对话进行摘要 | 40%-70% | ⚠️ 部分实现 |
| 向量检索记忆 (RAG-based Memory) | 检索相关记忆而非全量发送 | 50%-80% | ✅ 已实现 |
| 长短期记忆分离 | 分离当前任务和用户偏好 | 20%-40% | ⚠️ 部分实现 |

## 2. 当前系统实现分析

### 2.1 ✅ 已实现：向量检索记忆（RAG-based Memory）

**实现位置**：`core/memory/langgraph_store.py`

**实现细节**：
```python
# LongTermMemoryStore.search() - 向量语义搜索
async def search(
    self,
    user_id: str,
    query: str,
    limit: int = 10,
    memory_type: str | None = None,
) -> list[dict[str, Any]]:
    # 1. 使用向量数据库进行语义搜索
    vector_results = await self.vector_store.search(
        collection="memories",
        query=query,
        limit=limit * 2,
        query_filter={"user_id": user_id},
    )
    # 2. 从 LangGraph Store 获取完整元数据
    # 3. 按分数和重要性排序
```

**优化效果**：
- 每次调用只检索 5-10 条最相关记忆
- 避免全量发送历史记忆
- 预估节省 Token：50%-80%

### 2.2 ✅ 已实现：智能上下文压缩（Smart Context Compression）

**实现位置**：
- `core/context/smart_compressor.py` - 智能压缩器
- `core/context/manager.py` - 上下文管理器

**智能压缩策略**（替代简单滑动窗口）：

```
┌─────────────────────────────────────────────────────────────────┐
│                      智能上下文压缩流程                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 重要性评分                                                   │
│     ├─ 位置权重（首轮 +30, 最近 +25）                           │
│     ├─ 角色权重（用户消息 +10）                                 │
│     ├─ 工具调用 (+20)                                           │
│     ├─ 关键词匹配（决定/确定/最终 +15）                         │
│     └─ 内容特征（代码块 +12, 列表 +8）                          │
│                                                                  │
│  2. 保护区域                                                     │
│     ├─ 首轮保护：前 2 轮对话（任务定义）                        │
│     └─ 尾部保护：最近 6 条消息（连贯性）                        │
│                                                                  │
│  3. 压缩策略                                                     │
│     ├─ CRITICAL/HIGH 消息必须保留                               │
│     ├─ 中间低重要性消息 → 生成摘要                              │
│     └─ 按分数选择可选消息                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**消息重要性等级**：
| 等级 | 分数阈值 | 说明 |
|------|----------|------|
| CRITICAL | ≥50 | 关键消息（任务定义、最终决策） |
| HIGH | ≥35 | 高重要性（重要决策、关键信息） |
| MEDIUM | ≥20 | 中等重要性（正常对话） |
| LOW | ≥10 | 低重要性（简单确认、过渡语） |
| TRIVIAL | <10 | 可忽略（寒暄、重复内容） |

**Token 预算分配**：
- 系统提示词：2000 tokens（固定）
- 记忆预算：最多 20k tokens（20%）
- 历史消息预算：剩余部分（约 78k tokens）

**与简单滑动窗口的对比**：

| 特性 | 简单滑动窗口 | 智能压缩 |
|------|-------------|----------|
| 首轮保护 | ❌ | ✅ 保留任务定义 |
| 重要性评分 | ❌ | ✅ 多维度评分 |
| 摘要压缩 | ❌ | ✅ 自动生成摘要 |
| 上下文连贯性 | ❌ 直接截断 | ✅ 尾部保护 |
| 预估节省 | 30%-60% | 50%-80% |

### 2.3 ✅ 已实现：记忆总结（Summarization）

**实现位置**：
- `core/memory/summarizer.py` - 独立摘要器
- `core/context/smart_compressor.py` - 智能压缩器集成摘要

**实现细节**：

```python
# 自动触发摘要的条件
if original_tokens > budget * 0.7:  # 超过预算 70%
    summary = await self._summarize_middle_section(scored_messages, budget)

# 摘要内容
"""请简洁地总结以下对话的关键信息，保留：
1. 重要的决策和结论
2. 用户的偏好和要求
3. 关键的数据或事实"""
```

**摘要策略**：
1. ✅ 自动触发：超过 Token 阈值的 70% 时触发
2. ✅ 选择性摘要：只摘要中间部分的低重要性消息
3. ✅ 存储复用：摘要可存储到长期记忆
4. ✅ 作为上下文注入：`[之前对话摘要] ...`

### 2.4 ⚠️ 部分实现：长短期记忆分离

**当前实现**：
- **短期记忆**：LangGraph checkpointer（`core/engine/langgraph_checkpointer.py`）
- **长期记忆**：LongTermMemoryStore（`core/memory/langgraph_store.py`）

**当前问题**：
1. 缺少明确的记忆分类策略
2. 短期记忆没有自动过期机制
3. 长期记忆提取策略过于简单

### 2.5 ❌ 未实现：提示词缓存（Prompt Caching）

**重要性**：这是 2026 年最有效的 Token 成本优化手段。

**支持的云厂商**：
| 厂商 | 缓存折扣 | API 参数 |
|------|----------|----------|
| OpenAI | 50% | 自动（无需配置） |
| Anthropic | 90% | `cache_control` |
| DeepSeek | 50% | `cache_control` |

**当前缺失**：
1. 没有利用厂商提供的缓存 API
2. 系统提示词每次都完整发送
3. 没有缓存状态监控

## 3. 优化实施方案

### 3.1 提示词缓存实现方案

#### 3.1.1 核心原理

```
首次请求：
┌────────────────────────────────────────────┐
│ System Prompt (2000 tokens) - 完整计费     │
│ Memory Context (500 tokens) - 完整计费     │
│ User Message (100 tokens) - 完整计费       │
└────────────────────────────────────────────┘
总计费：2600 tokens × $0.001 = $0.0026

后续请求（使用缓存）：
┌────────────────────────────────────────────┐
│ System Prompt (2000 tokens) - 缓存命中 10% │
│ Memory Context (500 tokens) - 缓存命中 10% │
│ User Message (100 tokens) - 完整计费       │
└────────────────────────────────────────────┘
总计费：250 + 50 + 100 = 400 tokens 等价成本
```

#### 3.1.2 实现代码

**新增文件**：`core/llm/prompt_cache.py`

```python
"""
Prompt Cache Manager - 提示词缓存管理器

实现云厂商的提示词缓存功能，支持：
- Anthropic: cache_control API
- DeepSeek: cache_control API
- OpenAI: 自动缓存（无需特殊处理）
"""

from typing import Any, Literal
from dataclasses import dataclass
from datetime import datetime, UTC
import hashlib

from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CacheableContent:
    """可缓存的内容"""
    content: str
    cache_type: Literal["ephemeral", "persistent"] = "ephemeral"
    priority: int = 0  # 缓存优先级，越高越优先保留


class PromptCacheManager:
    """
    提示词缓存管理器

    设计原则：
    1. 系统提示词优先缓存（变化频率最低）
    2. 长期记忆次优先（用户偏好等稳定信息）
    3. 短期上下文不缓存（变化频繁）
    """

    # 各厂商的缓存配置
    PROVIDER_CACHE_CONFIG = {
        "anthropic": {
            "enabled": True,
            "discount": 0.1,  # 缓存命中时只收 10%
            "api_param": "cache_control",
            "min_tokens": 1024,  # 最小缓存 token 数
            "max_cache_points": 4,  # 最多 4 个缓存断点
        },
        "deepseek": {
            "enabled": True,
            "discount": 0.1,
            "api_param": "cache_control",
            "min_tokens": 64,
            "max_cache_points": 1,
        },
        "openai": {
            "enabled": True,
            "discount": 0.5,  # OpenAI 缓存折扣 50%
            "api_param": None,  # OpenAI 自动缓存，无需特殊参数
            "min_tokens": 1024,
            "max_cache_points": 0,
        },
    }

    def __init__(self) -> None:
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "estimated_savings": 0.0,
        }

    def get_provider_from_model(self, model: str) -> str:
        """根据模型名称推断提供商"""
        model_lower = model.lower()
        if "claude" in model_lower:
            return "anthropic"
        elif "deepseek" in model_lower:
            return "deepseek"
        elif "gpt" in model_lower or model_lower.startswith("o1"):
            return "openai"
        return "unknown"

    def prepare_cacheable_messages(
        self,
        messages: list[dict[str, Any]],
        model: str,
        system_prompt: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        准备可缓存的消息列表

        对于支持缓存的提供商，在适当位置添加 cache_control 标记。

        缓存策略：
        1. 系统提示词（如果存在且足够长）
        2. 前几条消息（上下文建立阶段）

        Args:
            messages: 原始消息列表
            model: 模型名称
            system_prompt: 系统提示词（可选，如果消息列表中没有）

        Returns:
            添加了缓存标记的消息列表
        """
        provider = self.get_provider_from_model(model)
        config = self.PROVIDER_CACHE_CONFIG.get(provider, {})

        if not config.get("enabled"):
            return messages

        api_param = config.get("api_param")
        if not api_param:
            # OpenAI 自动缓存，直接返回
            return messages

        min_tokens = config.get("min_tokens", 1024)
        max_cache_points = config.get("max_cache_points", 1)

        # 复制消息列表，避免修改原始数据
        cached_messages = []
        cache_points_used = 0

        for i, msg in enumerate(messages):
            msg_copy = msg.copy()

            # 只对系统消息和早期用户消息添加缓存标记
            if msg_copy.get("role") == "system" and cache_points_used < max_cache_points:
                content = msg_copy.get("content", "")
                # 检查是否满足最小 token 要求
                if len(content) >= min_tokens * 4:  # 粗略估算：1 token ≈ 4 字符
                    msg_copy["cache_control"] = {"type": "ephemeral"}
                    cache_points_used += 1
                    logger.debug(
                        "Added cache control to system message (cache point %d/%d)",
                        cache_points_used, max_cache_points
                    )

            cached_messages.append(msg_copy)

        return cached_messages

    def format_for_anthropic(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """
        格式化消息为 Anthropic API 格式

        Anthropic 的 system 参数需要单独传递，不在 messages 中。

        Returns:
            (system_prompt, messages)
        """
        system = system_prompt
        formatted_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                # 提取系统消息
                system = msg.get("content", "")
                continue

            formatted_msg = {
                "role": msg.get("role"),
                "content": msg.get("content"),
            }

            # 保留 cache_control（如果有）
            if "cache_control" in msg:
                # Anthropic 的 cache_control 需要放在 content 块中
                formatted_msg["content"] = [
                    {
                        "type": "text",
                        "text": msg.get("content"),
                        "cache_control": msg["cache_control"],
                    }
                ]

            formatted_messages.append(formatted_msg)

        return system, formatted_messages

    def format_for_deepseek(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        格式化消息为 DeepSeek API 格式

        DeepSeek 使用类似 Anthropic 的 cache_control 参数。
        注意：DeepSeek 只支持对 system 消息进行缓存。
        """
        formatted_messages = []

        for msg in messages:
            formatted_msg = msg.copy()

            # DeepSeek 的 cache_control 放在消息级别
            if "cache_control" in msg and msg.get("role") == "system":
                # 保持 cache_control 在消息级别
                pass
            elif "cache_control" in msg:
                # 非系统消息移除 cache_control
                del formatted_msg["cache_control"]

            formatted_messages.append(formatted_msg)

        return formatted_messages

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        return {
            **self._cache_stats,
            "hit_rate": (
                self._cache_stats["hits"] /
                (self._cache_stats["hits"] + self._cache_stats["misses"])
                if (self._cache_stats["hits"] + self._cache_stats["misses"]) > 0
                else 0
            ),
        }

    def update_stats(
        self,
        usage: dict[str, int] | None,
        provider: str,
    ) -> None:
        """
        更新缓存统计

        根据 API 响应中的 usage 信息判断缓存命中情况。
        """
        if not usage:
            return

        # Anthropic 返回 cache_read_input_tokens
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)

        if cache_read > 0:
            self._cache_stats["hits"] += 1
            # 估算节省的成本
            config = self.PROVIDER_CACHE_CONFIG.get(provider, {})
            discount = config.get("discount", 0.5)
            savings = cache_read * (1 - discount)
            self._cache_stats["estimated_savings"] += savings
            logger.info(
                "Cache hit! Read %d tokens from cache, saved ~%d token equivalents",
                cache_read, int(savings)
            )
        elif cache_creation > 0:
            self._cache_stats["misses"] += 1
            logger.info("Cache miss, created cache with %d tokens", cache_creation)


# 全局缓存管理器实例
_prompt_cache_manager: PromptCacheManager | None = None


def get_prompt_cache_manager() -> PromptCacheManager:
    """获取全局缓存管理器"""
    global _prompt_cache_manager
    if _prompt_cache_manager is None:
        _prompt_cache_manager = PromptCacheManager()
    return _prompt_cache_manager
```

#### 3.1.3 集成到 LLM Gateway

**修改文件**：`core/llm/gateway.py`

在 `chat` 方法中添加缓存处理：

```python
from core.llm.prompt_cache import get_prompt_cache_manager

async def chat(
    self,
    messages: list[dict[str, Any]],
    model: str | None = None,
    # ... 其他参数
    enable_cache: bool = True,  # 新增：是否启用缓存
) -> LLMResponse:
    model = model or self.config.default_model

    # 应用提示词缓存
    if enable_cache:
        cache_manager = get_prompt_cache_manager()
        messages = cache_manager.prepare_cacheable_messages(
            messages=messages,
            model=model,
        )

    # ... 继续原有逻辑
```

### 3.2 记忆总结自动化方案

#### 3.2.1 设计目标

1. 当对话 Token 超过阈值时自动触发摘要
2. 摘要结果存储到长期记忆
3. 使用摘要替代原始历史

#### 3.2.2 实现代码

**新增文件**：`core/memory/summarizer.py`

```python
"""
Memory Summarizer - 记忆摘要器

负责：
1. 监控对话长度
2. 自动触发摘要
3. 管理摘要生命周期
"""

from typing import Any
from dataclasses import dataclass
from datetime import datetime, UTC

from core.llm.gateway import LLMGateway
from core.memory.langgraph_store import LongTermMemoryStore
from core.types import Message, MessageRole
from utils.logging import get_logger
from utils.tokens import count_tokens

logger = get_logger(__name__)


@dataclass
class SummarizationConfig:
    """摘要配置"""
    # Token 阈值（超过此值触发摘要）
    token_threshold: int = 8000
    # 摘要保留的最近消息数
    preserve_recent_messages: int = 4
    # 摘要最大 Token 数
    max_summary_tokens: int = 500
    # 是否存储到长期记忆
    store_to_long_term: bool = True


SUMMARIZATION_PROMPT = """请对以下对话进行摘要，保留关键信息：

1. 用户的主要意图和需求
2. 重要的决策和结论
3. 待办事项或后续步骤
4. 关键的数据或事实

对话内容：
{conversation}

请用简洁的中文输出摘要（最多 500 字）："""


class MemorySummarizer:
    """
    记忆摘要器

    负责在对话过长时自动生成摘要，压缩上下文。
    """

    def __init__(
        self,
        llm_gateway: LLMGateway,
        memory_store: LongTermMemoryStore | None = None,
        config: SummarizationConfig | None = None,
    ) -> None:
        self.llm_gateway = llm_gateway
        self.memory_store = memory_store
        self.config = config or SummarizationConfig()

    def should_summarize(self, messages: list[Message]) -> bool:
        """
        判断是否需要摘要

        条件：
        1. 消息数量 > 保留数量
        2. Token 总数 > 阈值
        """
        if len(messages) <= self.config.preserve_recent_messages:
            return False

        total_tokens = sum(self._estimate_message_tokens(m) for m in messages)
        return total_tokens > self.config.token_threshold

    async def summarize_and_compress(
        self,
        messages: list[Message],
        user_id: str,
        session_id: str,
    ) -> tuple[str, list[Message]]:
        """
        执行摘要并压缩消息

        Args:
            messages: 原始消息列表
            user_id: 用户 ID
            session_id: 会话 ID

        Returns:
            (摘要文本, 压缩后的消息列表)
        """
        if not self.should_summarize(messages):
            return "", messages

        # 分离要摘要的消息和要保留的消息
        preserve_count = self.config.preserve_recent_messages
        messages_to_summarize = messages[:-preserve_count]
        messages_to_preserve = messages[-preserve_count:]

        # 生成摘要
        summary = await self._generate_summary(messages_to_summarize)

        # 存储摘要到长期记忆
        if self.config.store_to_long_term and self.memory_store:
            await self._store_summary(
                summary=summary,
                user_id=user_id,
                session_id=session_id,
                message_count=len(messages_to_summarize),
            )

        # 构建压缩后的消息列表
        compressed_messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=f"[之前对话摘要]\n{summary}",
            ),
            *messages_to_preserve,
        ]

        logger.info(
            "Summarized %d messages into %d tokens, preserved %d recent messages",
            len(messages_to_summarize),
            count_tokens(summary),
            preserve_count,
        )

        return summary, compressed_messages

    async def _generate_summary(
        self,
        messages: list[Message],
    ) -> str:
        """生成摘要"""
        # 格式化对话
        conversation_text = "\n".join(
            f"{m.role.value}: {m.content or '[工具调用]'}"
            for m in messages
        )

        # 调用 LLM 生成摘要
        prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text)

        response = await self.llm_gateway.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.config.max_summary_tokens,
            temperature=0.3,  # 低温度确保摘要稳定
        )

        return response.content or ""

    async def _store_summary(
        self,
        summary: str,
        user_id: str,
        session_id: str,
        message_count: int,
    ) -> None:
        """存储摘要到长期记忆"""
        if not self.memory_store:
            return

        await self.memory_store.put(
            user_id=user_id,
            memory_type="session_summary",
            content=summary,
            importance=7.0,  # 摘要重要性较高
            metadata={
                "session_id": session_id,
                "summarized_message_count": message_count,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )

    def _estimate_message_tokens(self, message: Message) -> int:
        """估算消息 Token 数"""
        tokens = 4  # 消息格式开销
        if message.content:
            tokens += count_tokens(message.content)
        return tokens
```

### 3.3 长短期记忆优化方案

#### 3.3.1 记忆分类策略

```
┌─────────────────────────────────────────────────────────────────┐
│                        记忆分层架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐                                           │
│  │   工作记忆        │  ← 当前会话上下文（LangGraph State）      │
│  │  (Working Memory) │    生命周期：单次对话                     │
│  └────────┬─────────┘    存储：内存                             │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │   短期记忆        │  ← 会话历史（LangGraph Checkpointer）     │
│  │  (Short-term)    │    生命周期：24小时 - 7天                 │
│  └────────┬─────────┘    存储：Redis/PostgreSQL                 │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐                                           │
│  │   长期记忆        │  ← 用户偏好、事实（LongTermMemoryStore） │
│  │  (Long-term)     │    生命周期：永久                         │
│  └──────────────────┘    存储：向量数据库 + PostgreSQL           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 实现代码

**新增文件**：`core/memory/tiered_memory.py`

```python
"""
Tiered Memory Manager - 分层记忆管理器

实现工作记忆、短期记忆、长期记忆的分层管理
"""

from typing import Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta

from core.memory.langgraph_store import LongTermMemoryStore
from core.engine.langgraph_checkpointer import LangGraphCheckpointer
from utils.logging import get_logger

logger = get_logger(__name__)


class MemoryTier(Enum):
    """记忆层级"""
    WORKING = "working"      # 工作记忆（当前上下文）
    SHORT_TERM = "short"     # 短期记忆（会话历史）
    LONG_TERM = "long"       # 长期记忆（永久存储）


class MemoryType(Enum):
    """记忆类型"""
    # 工作记忆
    CURRENT_TASK = "current_task"       # 当前任务
    TOOL_RESULTS = "tool_results"       # 工具结果

    # 短期记忆
    SESSION_CONTEXT = "session_context" # 会话上下文
    RECENT_DECISIONS = "recent_decisions" # 近期决策

    # 长期记忆
    USER_PREFERENCE = "preference"      # 用户偏好
    FACTUAL_KNOWLEDGE = "fact"          # 事实知识
    PROCEDURE = "procedure"             # 操作步骤
    SESSION_SUMMARY = "session_summary" # 会话摘要


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


@dataclass
class TieredMemoryConfig:
    """分层记忆配置"""
    # 短期记忆 TTL
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


class TieredMemoryManager:
    """
    分层记忆管理器

    协调工作记忆、短期记忆、长期记忆的存取
    """

    def __init__(
        self,
        long_term_store: LongTermMemoryStore,
        checkpointer: LangGraphCheckpointer,
        config: TieredMemoryConfig | None = None,
    ) -> None:
        self.long_term_store = long_term_store
        self.checkpointer = checkpointer
        self.config = config or TieredMemoryConfig()

        # 工作记忆（内存中）
        self._working_memory: dict[str, list[MemoryItem]] = {}

    async def recall(
        self,
        user_id: str,
        session_id: str,
        query: str,
        tiers: list[MemoryTier] | None = None,
        limit: int = 10,
    ) -> list[MemoryItem]:
        """
        召回记忆

        从指定层级中检索相关记忆，按相关性和重要性排序

        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            query: 查询文本
            tiers: 要搜索的层级（默认所有）
            limit: 返回数量

        Returns:
            排序后的记忆列表
        """
        tiers = tiers or list(MemoryTier)
        all_memories: list[tuple[MemoryItem, float]] = []

        for tier in tiers:
            tier_memories = await self._recall_from_tier(
                tier=tier,
                user_id=user_id,
                session_id=session_id,
                query=query,
                limit=limit,
            )

            # 应用层级权重
            weight = self.config.recall_weights.get(tier, 0.5)
            for memory, score in tier_memories:
                all_memories.append((memory, score * weight))

        # 按加权分数排序
        all_memories.sort(key=lambda x: x[1], reverse=True)

        return [m for m, _ in all_memories[:limit]]

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
        """召回工作记忆"""
        memories = self._working_memory.get(session_id, [])
        # 简单的关键词匹配（工作记忆较小，不需要向量搜索）
        results = []
        for memory in memories:
            if query.lower() in memory.content.lower():
                results.append((memory, 1.0))
        return results[:limit]

    async def _recall_short_term(
        self,
        session_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[MemoryItem, float]]:
        """召回短期记忆"""
        # 从 checkpointer 获取会话历史
        # 这里需要根据实际的 checkpointer 实现来获取
        # 暂时返回空列表
        return []

    async def _recall_long_term(
        self,
        user_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[MemoryItem, float]]:
        """召回长期记忆"""
        results = await self.long_term_store.search(
            user_id=user_id,
            query=query,
            limit=limit,
        )

        memories = []
        for r in results:
            memory = MemoryItem(
                id=r["id"],
                tier=MemoryTier.LONG_TERM,
                type=MemoryType(r.get("type", "fact")),
                content=r["content"],
                importance=r.get("importance", 5.0),
                metadata=r.get("metadata", {}),
            )
            memories.append((memory, r.get("score", 0.5)))

        return memories

    async def store(
        self,
        user_id: str,
        session_id: str,
        memory: MemoryItem,
    ) -> str:
        """
        存储记忆

        根据记忆类型和重要性决定存储位置
        """
        if memory.tier == MemoryTier.WORKING:
            return self._store_working_memory(session_id, memory)
        elif memory.tier == MemoryTier.LONG_TERM:
            return await self._store_long_term(user_id, memory)

        return memory.id

    def _store_working_memory(
        self,
        session_id: str,
        memory: MemoryItem,
    ) -> str:
        """存储工作记忆"""
        if session_id not in self._working_memory:
            self._working_memory[session_id] = []
        self._working_memory[session_id].append(memory)
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

        return await self.long_term_store.put(
            user_id=user_id,
            memory_type=memory.type.value,
            content=memory.content,
            importance=memory.importance,
            metadata=memory.metadata,
        )

    def clear_working_memory(self, session_id: str) -> None:
        """清空工作记忆"""
        if session_id in self._working_memory:
            del self._working_memory[session_id]

    async def promote_to_long_term(
        self,
        user_id: str,
        session_id: str,
        memory_id: str,
    ) -> str | None:
        """
        将短期记忆提升为长期记忆

        当某条短期记忆被反复引用时，可以提升为长期记忆
        """
        # 从工作记忆中查找
        if session_id in self._working_memory:
            for memory in self._working_memory[session_id]:
                if memory.id == memory_id:
                    memory.tier = MemoryTier.LONG_TERM
                    return await self._store_long_term(user_id, memory)
        return None
```

## 4. 集成方案

### 4.1 修改 LangGraph Agent Engine

在 `core/engine/langgraph_agent.py` 中集成上述优化：

```python
from core.llm.prompt_cache import get_prompt_cache_manager
from core.memory.summarizer import MemorySummarizer, SummarizationConfig

class LangGraphAgentEngine:
    def __init__(self, ...):
        # ... 现有代码

        # 新增：提示词缓存管理器
        self.cache_manager = get_prompt_cache_manager()

        # 新增：记忆摘要器
        self.summarizer = MemorySummarizer(
            llm_gateway=llm_gateway,
            memory_store=memory_store,
            config=SummarizationConfig(
                token_threshold=8000,
                preserve_recent_messages=4,
            ),
        )

    async def _call_llm(self, state: AgentState) -> dict[str, Any]:
        # ... 构建 lite_messages

        # 应用提示词缓存
        lite_messages = self.cache_manager.prepare_cacheable_messages(
            messages=lite_messages,
            model=self.config.model,
        )

        # 调用 LLM
        response = await self.llm_gateway.chat(
            messages=lite_messages,
            # ...
        )

        # 更新缓存统计
        if response.usage:
            provider = self.cache_manager.get_provider_from_model(self.config.model)
            self.cache_manager.update_stats(response.usage, provider)

        # ... 继续处理响应
```

### 4.2 修改配置

在 `app/config.py` 中添加优化相关配置：

```python
class Settings(BaseSettings):
    # ... 现有配置

    # ========================================================================
    # Token 优化配置
    # ========================================================================
    # 提示词缓存
    prompt_cache_enabled: bool = True

    # 记忆摘要
    memory_summarization_enabled: bool = True
    memory_summarization_threshold: int = 8000  # Token 阈值

    # 分层记忆
    tiered_memory_enabled: bool = True
    short_term_memory_ttl_hours: int = 24
    long_term_importance_threshold: float = 6.0
```

## 5. 效果预估

### 5.1 成本节省预估

| 场景 | 优化前 (tokens) | 优化后 (tokens) | 节省比例 |
|------|----------------|----------------|----------|
| 首次对话 | 5,000 | 5,000 | 0% |
| 第 5 轮对话 | 15,000 | 8,000 | 47% |
| 第 10 轮对话 | 30,000 | 10,000 | 67% |
| 第 20 轮对话 | 60,000 | 12,000 | 80% |

### 5.2 延迟优化

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 首次响应延迟 | 2.0s | 2.0s |
| 缓存命中响应 | 2.0s | 1.2s |
| 长对话响应 | 5.0s | 2.5s |

## 6. 实施优先级

### Phase 1（高优先级）- 预计 2 周

1. ✅ 实现 `PromptCacheManager`
2. ✅ 集成到 `LLMGateway`
3. ✅ 添加缓存统计和监控

### Phase 2（中优先级）- 预计 2 周

1. ✅ 实现 `MemorySummarizer`
2. ✅ 自动触发摘要逻辑
3. ✅ 摘要存储到长期记忆

### Phase 3（中优先级）- 预计 3 周

1. ✅ 实现 `TieredMemoryManager`
2. ✅ 优化记忆分类策略
3. ✅ 实现记忆提升机制

### Phase 4（持续优化）

1. Token 使用监控面板
2. 自动成本报告
3. A/B 测试不同策略

## 7. 监控指标

建议添加以下监控指标：

```python
# Prometheus 指标
from prometheus_client import Counter, Histogram, Gauge

# Token 使用统计
token_usage_total = Counter(
    "agent_token_usage_total",
    "Total tokens used",
    ["model", "type"]  # type: input/output/cached
)

# 缓存命中率
cache_hit_rate = Gauge(
    "agent_cache_hit_rate",
    "Prompt cache hit rate"
)

# 摘要触发次数
summarization_count = Counter(
    "agent_summarization_total",
    "Number of summarizations performed"
)

# 成本节省估算
estimated_savings = Counter(
    "agent_token_savings_total",
    "Estimated tokens saved by optimizations"
)
```

## 8. 总结

当前系统已实现 **向量检索记忆** 和 **滑动窗口** 两个核心优化策略，但缺少最重要的 **提示词缓存** 功能。

**建议优先实施**：
1. 提示词缓存（成本节省 50%-90%）
2. 记忆总结自动化（当前已有代码但未启用）
3. 分层记忆管理（提升记忆检索效率）

通过以上优化，预计可以将 Token 成本降低 **60%-80%**，同时提升响应速度 **30%-50%**。
