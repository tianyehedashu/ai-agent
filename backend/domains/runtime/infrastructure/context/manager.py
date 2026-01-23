"""
Context Manager - 上下文管理器实现

负责:
- 组装完整上下文 (System + History + Memory)
- Token 预算管理
- 智能上下文压缩（首轮保护、重要性评分、摘要）
"""

from typing import TYPE_CHECKING, Any

from domains.runtime.infrastructure.context.smart_compressor import (
    CompressionConfig,
    CompressionResult,
    SmartContextCompressor,
)
from shared.types import AgentConfig, Message
from shared.infrastructure.utils.message_formatter import estimate_message_tokens, format_message
from utils.logging import get_logger
from utils.tokens import count_tokens, truncate_to_token_limit

if TYPE_CHECKING:
    from shared.infrastructure.llm.gateway import LLMGateway

logger = get_logger(__name__)


class ContextManager:
    """
    上下文管理器

    负责组装和管理 Agent 执行所需的上下文。

    智能压缩策略（替代简单滑动窗口）：
    1. 首轮保护 - 保留任务定义和初始上下文
    2. 重要性评分 - 根据内容特征判断消息重要性
    3. 摘要压缩 - 将低重要性的早期对话压缩为摘要
    4. 尾部保护 - 保留最近消息确保连贯性
    """

    def __init__(
        self,
        config: AgentConfig,
        max_context_tokens: int = 100000,
        llm_gateway: "LLMGateway | None" = None,
        enable_smart_compression: bool = True,
    ) -> None:
        """
        初始化上下文管理器

        Args:
            config: Agent 配置
            max_context_tokens: 最大上下文 Token 数
            llm_gateway: LLM 网关（用于智能摘要）
            enable_smart_compression: 是否启用智能压缩
        """
        self.config = config
        self.max_context_tokens = max_context_tokens
        self.llm_gateway = llm_gateway
        self.enable_smart_compression = enable_smart_compression

        # Token 预算分配
        # 如果 max_context_tokens 太小，按比例分配
        if max_context_tokens < 10000:
            # 小预算：系统 20%，记忆 40%，历史 40%
            self.system_budget = int(max_context_tokens * 0.2)
            self.memory_budget = int(max_context_tokens * 0.4)
            self.history_budget = max_context_tokens - self.system_budget - self.memory_budget
        else:
            # 大预算（100k+）：动态分配
            # 系统提示词：固定 2000 tokens
            self.system_budget = 2000
            # 记忆预算：根据上下文大小动态调整（最多 20k tokens，用于存储大量相关记忆）
            # 对于 100k 上下文，分配 20% 给记忆，这样可以存储更多相关记忆
            self.memory_budget = min(20000, int(max_context_tokens * 0.2))
            # 历史消息预算：剩余部分
            self.history_budget = max_context_tokens - self.system_budget - self.memory_budget

        # 确保 history_budget 至少为 0
        self.history_budget = max(0, self.history_budget)

        # 初始化智能压缩器
        self._compressor = SmartContextCompressor(
            llm_gateway=llm_gateway,
            config=CompressionConfig(
                max_history_tokens=self.history_budget,
                protect_first_n_turns=2,
                protect_last_n_messages=6,
                enable_summarization=True,
                summarization_threshold=0.7,
            ),
        )

        # 上次压缩结果（用于监控）
        self._last_compression_result: CompressionResult | None = None

    def build_context(
        self,
        messages: list[Message],
        memories: list[str] | None = None,
        tools_context: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        构建完整上下文

        Args:
            messages: 对话历史
            memories: 相关记忆
            tools_context: 工具上下文

        Returns:
            格式化的消息列表
        """
        context: list[dict[str, Any]] = []

        # 1. 系统提示词
        system_content = self._build_system_prompt(
            memories=memories,
            tools_context=tools_context,
        )
        context.append(
            {
                "role": "system",
                "content": system_content,
            }
        )

        # 2. 对话历史 (智能压缩或简单裁剪)
        history = self._trim_history(messages)
        for msg in history:
            context.append(self._format_message(msg))

        return context

    async def build_context_async(
        self,
        messages: list[Message],
        memories: list[str] | None = None,
        tools_context: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        异步构建完整上下文（支持智能摘要）

        与 build_context 的区别：
        - 支持异步摘要生成
        - 使用智能压缩器

        Args:
            messages: 对话历史
            memories: 相关记忆
            tools_context: 工具上下文

        Returns:
            格式化的消息列表
        """
        context: list[dict[str, Any]] = []

        # 1. 系统提示词
        system_content = self._build_system_prompt(
            memories=memories,
            tools_context=tools_context,
        )
        context.append(
            {
                "role": "system",
                "content": system_content,
            }
        )

        # 2. 智能压缩对话历史（传入召回的记忆用于去重优化）
        if self.enable_smart_compression:
            result = await self._compressor.compress(
                messages,
                self.history_budget,
                recalled_memories=memories,  # SimpleMem 协同：避免重复信息
            )
            self._last_compression_result = result

            # 如果有摘要，添加为系统消息
            if result.summary:
                context.append(
                    {
                        "role": "system",
                        "content": f"[之前对话摘要]\n{result.summary}",
                    }
                )

            # 添加保留的消息
            for msg in result.messages:
                context.append(self._format_message(msg))

            logger.info(
                "Smart compression: %d -> %d messages, %d -> %d tokens (%.1f%% saved)",
                result.original_count,
                result.compressed_count,
                result.original_tokens,
                result.compressed_tokens,
                result.compression_ratio * 100,
            )
        else:
            # 降级到简单裁剪
            history = self._trim_history(messages)
            for msg in history:
                context.append(self._format_message(msg))

        return context

    def _build_system_prompt(
        self,
        memories: list[str] | None = None,
        tools_context: str | None = None,
    ) -> str:
        """构建系统提示词"""
        parts = []

        # 基础系统提示词
        if self.config.system_prompt:
            parts.append(self.config.system_prompt)
        else:
            parts.append(self._default_system_prompt())

        # 记忆上下文（智能裁剪，充分利用 memory_budget）
        if memories:
            # 按重要性排序，优先保留重要记忆
            # 注意：memories 已经是字符串列表，按顺序添加直到达到预算
            memory_text_parts = []
            current_tokens = 0

            for memory in memories:
                memory_line = f"- {memory}"
                memory_tokens = count_tokens(memory_line)

                # 如果添加这条记忆会超出预算，停止添加
                if current_tokens + memory_tokens > self.memory_budget:
                    break

                memory_text_parts.append(memory_line)
                current_tokens += memory_tokens

            if memory_text_parts:
                parts.append(
                    f"\n## 相关记忆（共 {len(memory_text_parts)}/{len(memories)} 条）\n"
                    + "\n".join(memory_text_parts)
                )

        # 工具上下文
        if tools_context:
            parts.append(f"\n## 可用工具\n{tools_context}")

        # 裁剪到预算（确保不超过 system_budget）
        full_prompt = "\n\n".join(parts)
        return truncate_to_token_limit(full_prompt, self.system_budget)

    def _default_system_prompt(self) -> str:
        """默认系统提示词"""
        return """你是一个智能 AI 助手，能够帮助用户完成各种任务。

## 核心能力
- 理解用户意图并提供帮助
- 使用工具完成具体任务
- 持续学习和适应

## 工作原则
1. 始终尝试帮助用户解决问题
2. 如果需要使用工具，请明确说明原因
3. 如果遇到错误，尝试其他方法
4. 保持回答简洁、准确

## 输出格式
- 使用 Markdown 格式
- 代码使用代码块
- 关键信息使用粗体"""

    def _trim_history(self, messages: list[Message]) -> list[Message]:
        """裁剪对话历史到预算范围"""
        if not messages:
            return []

        # 从最新消息开始，向前累计
        trimmed: list[Message] = []
        total_tokens = 0

        for msg in reversed(messages):
            msg_tokens = estimate_message_tokens(msg)

            if total_tokens + msg_tokens > self.history_budget:
                break

            trimmed.insert(0, msg)
            total_tokens += msg_tokens

        logger.debug("Trimmed history: %d -> %d messages", len(messages), len(trimmed))
        return trimmed

    def _format_message(self, message: Message) -> dict[str, Any]:
        """格式化消息（复用公共函数）"""
        return format_message(message)

    def get_remaining_budget(self, current_messages: list[Message]) -> int:
        """获取剩余 token 预算"""
        used = sum(estimate_message_tokens(m) for m in current_messages)
        return max(0, self.max_context_tokens - self.system_budget - used)

    def should_summarize(self, messages: list[Message]) -> bool:
        """判断是否需要摘要压缩"""
        total_tokens = sum(estimate_message_tokens(m) for m in messages)
        return total_tokens > self.history_budget * 0.8

    async def summarize_history(
        self,
        messages: list[Message],
        llm_gateway: Any,
    ) -> str:
        """
        生成对话摘要

        当历史过长时使用
        """
        # 构建摘要请求
        history_text = "\n".join(f"{m.role.value}: {m.content or '[tool call]'}" for m in messages)

        response = await llm_gateway.chat(
            messages=[
                {
                    "role": "system",
                    "content": "请简洁地总结以下对话的关键信息，保留重要的决策和结果。",
                },
                {
                    "role": "user",
                    "content": history_text,
                },
            ],
            max_tokens=500,
        )

        return response.content or ""

    def get_compression_stats(self) -> dict[str, Any] | None:
        """
        获取上次压缩的统计信息

        Returns:
            压缩统计，如果没有则返回 None
        """
        if not self._last_compression_result:
            return None

        result = self._last_compression_result
        return {
            "original_count": result.original_count,
            "compressed_count": result.compressed_count,
            "original_tokens": result.original_tokens,
            "compressed_tokens": result.compressed_tokens,
            "compression_ratio": result.compression_ratio,
            "dropped_messages": result.dropped_messages,
            "summarized_messages": result.summarized_messages,
            "has_summary": result.summary is not None,
        }

    def get_compression_preview(
        self,
        messages: list[Message],
    ) -> dict[str, Any]:
        """
        获取压缩预览

        用于 UI 展示每条消息的重要性评分。

        Args:
            messages: 消息列表

        Returns:
            预览信息，包含每条消息的重要性评分
        """
        return self._compressor.get_compression_preview(messages, self.history_budget)

    def set_llm_gateway(self, llm_gateway: "LLMGateway") -> None:
        """
        设置 LLM 网关

        用于延迟初始化或更新 LLM 网关。

        Args:
            llm_gateway: LLM 网关实例
        """
        self.llm_gateway = llm_gateway
        # 重新创建压缩器以使用新的 LLM 网关
        self._compressor = SmartContextCompressor(
            llm_gateway=llm_gateway,
            config=CompressionConfig(
                max_history_tokens=self.history_budget,
                protect_first_n_turns=2,
                protect_last_n_messages=6,
                enable_summarization=True,
                summarization_threshold=0.7,
            ),
        )
