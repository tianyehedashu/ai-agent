"""
Memory Summarizer - 记忆摘要器

负责：
1. 监控对话长度
2. 自动触发摘要
3. 管理摘要生命周期

当对话 Token 超过阈值时，自动生成摘要以压缩上下文，
这是 2026 年主流的 Token 优化策略之一，可以节省 40%-70% 的成本。
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from domains.agent.domain.types import (
    Message,
    MessageRole,
)
from utils.logging import get_logger
from utils.tokens import count_tokens

if TYPE_CHECKING:
    from domains.agent.infrastructure.llm.gateway import LLMGateway
    from domains.agent.infrastructure.memory.langgraph_store import LongTermMemoryStore

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
    # 摘要重要性（用于长期记忆存储）
    summary_importance: float = 7.0
    # 触发摘要的最小消息数
    min_messages_for_summary: int = 6


@dataclass
class SummarizationResult:
    """摘要结果"""

    summary: str
    original_message_count: int
    summarized_message_count: int
    preserved_message_count: int
    original_tokens: int
    compressed_tokens: int
    memory_id: str | None = None

    @property
    def compression_ratio(self) -> float:
        """压缩比"""
        if self.original_tokens == 0:
            return 0.0
        return 1 - (self.compressed_tokens / self.original_tokens)


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

    使用场景：
    1. 长对话场景（超过 8000 tokens）
    2. 节省 API 调用成本
    3. 提升响应速度

    摘要策略：
    1. 保留最近 N 条消息（保持上下文连贯性）
    2. 对旧消息生成摘要
    3. 将摘要作为系统消息注入
    """

    def __init__(
        self,
        llm_gateway: "LLMGateway",
        memory_store: "LongTermMemoryStore | None" = None,
        config: SummarizationConfig | None = None,
    ) -> None:
        """
        初始化记忆摘要器

        Args:
            llm_gateway: LLM 网关
            memory_store: 长期记忆存储（可选）
            config: 摘要配置
        """
        self.llm_gateway = llm_gateway
        self.memory_store = memory_store
        self.config = config or SummarizationConfig()

    def should_summarize(self, messages: list[Message]) -> bool:
        """
        判断是否需要摘要

        条件：
        1. 消息数量 > 保留数量 + 最小摘要消息数
        2. Token 总数 > 阈值

        Args:
            messages: 消息列表

        Returns:
            是否需要摘要
        """
        min_messages = self.config.preserve_recent_messages + self.config.min_messages_for_summary
        if len(messages) <= min_messages:
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

        # 计算原始 Token 数
        original_tokens = sum(self._estimate_message_tokens(m) for m in messages)

        # 生成摘要
        summary = await self._generate_summary(messages_to_summarize)

        # 存储摘要到长期记忆
        memory_id = None
        if self.config.store_to_long_term and self.memory_store:
            memory_id = await self._store_summary(
                summary=summary,
                user_id=user_id,
                session_id=session_id,
                message_count=len(messages_to_summarize),
            )

        # 构建压缩后的消息列表
        summary_message = Message(
            role=MessageRole.SYSTEM,
            content=f"[之前对话摘要]\n{summary}",
        )
        compressed_messages = [summary_message, *messages_to_preserve]

        # 计算压缩后 Token 数
        compressed_tokens = sum(self._estimate_message_tokens(m) for m in compressed_messages)

        # 记录摘要结果
        result = SummarizationResult(
            summary=summary,
            original_message_count=len(messages),
            summarized_message_count=len(messages_to_summarize),
            preserved_message_count=len(messages_to_preserve),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            memory_id=memory_id,
        )

        logger.info(
            "Summarized %d messages: %d -> %d tokens (%.1f%% compression)",
            result.summarized_message_count,
            result.original_tokens,
            result.compressed_tokens,
            result.compression_ratio * 100,
        )

        return summary, compressed_messages

    async def _generate_summary(
        self,
        messages: list[Message],
    ) -> str:
        """
        生成摘要

        Args:
            messages: 要摘要的消息列表

        Returns:
            摘要文本
        """
        # 格式化对话
        conversation_text = "\n".join(self._format_message(m) for m in messages)

        # 调用 LLM 生成摘要
        prompt = SUMMARIZATION_PROMPT.format(conversation=conversation_text)

        try:
            response = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.max_summary_tokens,
                temperature=0.3,  # 低温度确保摘要稳定
            )

            return response.content or ""
        except Exception as e:
            logger.error("Failed to generate summary: %s", e, exc_info=True)
            # 生成失败时返回简单摘要
            return self._generate_fallback_summary(messages)

    def _generate_fallback_summary(self, messages: list[Message]) -> str:
        """
        生成备用摘要（当 LLM 调用失败时）

        Args:
            messages: 消息列表

        Returns:
            简单摘要
        """
        # 提取前几条消息的内容
        summaries = []
        for msg in messages[:3]:
            if msg.content:
                # 截取前 100 字符
                content = msg.content[:100]
                if len(msg.content) > 100:
                    content += "..."
                summaries.append(f"- {msg.role.value}: {content}")

        return f"对话包含 {len(messages)} 条消息:\n" + "\n".join(summaries)

    async def _store_summary(
        self,
        summary: str,
        user_id: str,
        session_id: str,
        message_count: int,
    ) -> str | None:
        """
        存储摘要到长期记忆

        Args:
            summary: 摘要文本
            user_id: 用户 ID
            session_id: 会话 ID
            message_count: 被摘要的消息数

        Returns:
            记忆 ID 或 None
        """
        if not self.memory_store:
            return None

        try:
            return await self.memory_store.put(
                session_id=session_id,  # 记忆按会话隔离
                memory_type="session_summary",
                content=summary,
                importance=self.config.summary_importance,
                metadata={
                    "user_id": user_id,  # 保留 user_id 用于审计
                    "summarized_message_count": message_count,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as e:
            logger.error("Failed to store summary: %s", e, exc_info=True)
            return None

    def _format_message(self, message: Message) -> str:
        """
        格式化单条消息

        Args:
            message: 消息对象

        Returns:
            格式化的字符串
        """
        content = message.content or "[工具调用]"
        return f"{message.role.value}: {content}"

    def _estimate_message_tokens(self, message: Message) -> int:
        """
        估算消息 Token 数

        Args:
            message: 消息对象

        Returns:
            Token 数估算
        """
        tokens = 4  # 消息格式开销
        if message.content:
            tokens += count_tokens(message.content)
        return tokens

    def get_compression_estimate(self, messages: list[Message]) -> dict[str, int]:
        """
        估算压缩效果

        Args:
            messages: 消息列表

        Returns:
            包含估算信息的字典
        """
        if not self.should_summarize(messages):
            return {
                "needs_compression": False,
                "current_tokens": sum(self._estimate_message_tokens(m) for m in messages),
                "estimated_compressed_tokens": 0,
                "estimated_savings": 0,
            }

        preserve_count = self.config.preserve_recent_messages
        messages_to_preserve = messages[-preserve_count:]

        current_tokens = sum(self._estimate_message_tokens(m) for m in messages)
        preserved_tokens = sum(self._estimate_message_tokens(m) for m in messages_to_preserve)
        summary_tokens = self.config.max_summary_tokens  # 估算摘要 Token
        estimated_compressed = preserved_tokens + summary_tokens

        return {
            "needs_compression": True,
            "current_tokens": current_tokens,
            "estimated_compressed_tokens": estimated_compressed,
            "estimated_savings": current_tokens - estimated_compressed,
        }
