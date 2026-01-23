"""
Smart Context Manager - 智能上下文管理器

统一管理所有上下文优化组件：
1. KeyMessageDetector - 关键消息检测（基于 SimpleMem、PAACE）
2. PlanTracker - 计划追踪（基于 PAACE 的 plan-aware 策略）
3. SmartContextCompressor - 智能压缩（基于 Sculptor、Cognitive Workspace）
4. PromptCacheManager - 提示词缓存（利用云厂商 50%-90% 折扣）

参考论文（2025-2026）：
- PAACE: Plan-Aware Automated Agent Context Engineering (arXiv:2512.16970)
- SimpleMem: Efficient Lifelong Memory for LLM Agents (arXiv:2601.02553)
- Sculptor: Empowering LLMs with Active Context Management (arXiv:2508.04664)
- Cognitive Workspace: Active Memory Management for LLMs (arXiv:2508.13171)
- AgeMem: Agentic Memory unifying long/short-term memory (2026)

使用方法:
```python
manager = SmartContextManager(llm_gateway)
context = await manager.build_optimized_context(
    messages=conversation_history,
    recalled_memories=memories,
    system_prompt=prompt,
    model="claude-3-sonnet",
)
```
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from domains.agent.domain.types import (
    Message,
    MessageRole,
)
from domains.agent.infrastructure.context.key_detector import get_key_detector
from domains.agent.infrastructure.context.plan_tracker import PlanTracker
from domains.agent.infrastructure.context.smart_compressor import (
    CompressionConfig,
    CompressionResult,
    SmartContextCompressor,
)
from domains.agent.infrastructure.llm.prompt_cache import get_prompt_cache_manager
from utils.logging import get_logger
from utils.tokens import count_tokens

if TYPE_CHECKING:
    from domains.agent.infrastructure.llm.gateway import LLMGateway

logger = get_logger(__name__)


@dataclass
class SmartContextConfig:
    """智能上下文管理配置"""

    # 总 Token 预算
    max_context_tokens: int = 100000

    # 预算分配比例
    system_prompt_ratio: float = 0.15  # 系统提示词 15%
    memory_ratio: float = 0.10  # 记忆 10%
    history_ratio: float = 0.75  # 对话历史 75%

    # 压缩配置
    compression_enabled: bool = True
    protect_first_turns: int = 2  # 保护前 N 轮对话
    protect_last_messages: int = 6  # 保护最后 N 条消息
    summarize_threshold_ratio: float = 0.7  # 超过预算 70% 触发摘要

    # 缓存配置
    cache_enabled: bool = True

    # 计划追踪配置
    plan_tracking_enabled: bool = True


@dataclass
class ContextBuildResult:
    """上下文构建结果"""

    # 优化后的消息列表（可直接发送给 LLM）
    messages: list[dict[str, Any]]

    # 统计信息
    original_message_count: int = 0
    final_message_count: int = 0
    original_tokens: int = 0
    final_tokens: int = 0
    compression_ratio: float = 0.0

    # 生成的摘要（如果有）
    summary: str | None = None

    # 固定的消息索引
    pinned_indices: list[int] = field(default_factory=list)

    # 缓存信息
    cache_applied: bool = False
    cache_provider: str | None = None


class SmartContextManager:
    """
    智能上下文管理器

    整合关键消息检测、计划追踪、智能压缩、提示词缓存，
    提供统一的上下文构建接口。

    设计原则：
    1. 任务优先：任务定义和约束永不丢失
    2. 智能压缩：根据消息重要性动态压缩
    3. 成本优化：最大化利用云厂商缓存
    4. 透明可控：提供详细的统计和日志
    """

    def __init__(
        self,
        llm_gateway: "LLMGateway",
        config: SmartContextConfig | None = None,
    ) -> None:
        self.llm_gateway = llm_gateway
        self.config = config or SmartContextConfig()

        # 计算各部分 Token 预算
        self.system_budget = int(self.config.max_context_tokens * self.config.system_prompt_ratio)
        self.memory_budget = int(self.config.max_context_tokens * self.config.memory_ratio)
        self.history_budget = int(self.config.max_context_tokens * self.config.history_ratio)

        # 初始化组件
        self.key_detector = get_key_detector()
        self.plan_tracker = PlanTracker()
        self.compressor = SmartContextCompressor(
            llm_gateway=llm_gateway,
            config=CompressionConfig(
                max_history_tokens=self.history_budget,
                protect_first_n_turns=self.config.protect_first_turns,
                protect_last_n_messages=self.config.protect_last_messages,
                enable_summarization=True,
                summarization_threshold=self.config.summarize_threshold_ratio,
            ),
        )
        self.cache_manager = get_prompt_cache_manager()

        # 固定消息（跨轮次保留）
        self._pinned_message_ids: set[str] = set()

        logger.info(
            "SmartContextManager initialized: max_tokens=%d, system=%d, memory=%d, history=%d",
            self.config.max_context_tokens,
            self.system_budget,
            self.memory_budget,
            self.history_budget,
        )

    async def build_optimized_context(
        self,
        messages: list[Message],
        system_prompt: str,
        model: str,
        recalled_memories: list[dict[str, Any]] | None = None,
        tools_description: str | None = None,
    ) -> ContextBuildResult:
        """
        构建优化后的上下文

        Args:
            messages: 对话历史（Message 类型）
            system_prompt: 系统提示词
            model: 当前使用的 LLM 模型
            recalled_memories: 检索到的相关记忆
            tools_description: 工具描述（如果有）

        Returns:
            ContextBuildResult: 包含优化后的消息和统计信息
        """
        original_message_count = len(messages)
        original_tokens = sum(count_tokens(msg.content or "") for msg in messages)

        result = ContextBuildResult(
            messages=[],
            original_message_count=original_message_count,
            original_tokens=original_tokens,
        )

        # 1. 关键消息检测和固定
        pinned_indices = self._detect_and_pin_messages(messages)
        result.pinned_indices = pinned_indices

        # 2. 计划追踪更新
        if self.config.plan_tracking_enabled:
            self._update_plan_tracking(messages)

        # 3. 构建系统提示词
        system_content = self._build_system_content(
            base_prompt=system_prompt,
            recalled_memories=recalled_memories,
            tools_description=tools_description,
            plan_summary=self.plan_tracker.get_plan_summary()
            if self.config.plan_tracking_enabled
            else None,
        )

        # 4. 智能压缩对话历史
        compression_result: CompressionResult | None = None
        if self.config.compression_enabled:
            compression_result = await self.compressor.compress(
                messages=messages,
                budget_tokens=self.history_budget,
            )
            compressed_messages = compression_result.messages
        else:
            # 降级到简单裁剪
            compressed_messages = self._simple_trim(messages)

        # 5. 构建最终消息列表
        final_messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]

        # 检查是否有摘要
        if compression_result and compression_result.summary:
            result.summary = compression_result.summary
            # 摘要作为 assistant 消息插入
            final_messages.append(
                {
                    "role": "assistant",
                    "content": f"[之前对话摘要]\n{compression_result.summary}",
                }
            )

        # 添加压缩后的消息
        for msg in compressed_messages:
            final_messages.append(self._format_message(msg))

        # 6. 应用提示词缓存
        if self.config.cache_enabled and self.cache_manager.is_cache_supported(model):
            final_messages = self.cache_manager.prepare_cacheable_messages(
                messages=final_messages,
                model=model,
                system_prompt=system_content,
            )
            result.cache_applied = True
            result.cache_provider = self.cache_manager.get_provider_from_model(model)

        # 7. 计算统计信息
        result.messages = final_messages
        result.final_message_count = len(compressed_messages)
        result.final_tokens = sum(
            count_tokens(msg.get("content", "") or "") for msg in final_messages
        )
        if original_tokens > 0:
            result.compression_ratio = 1 - (result.final_tokens / original_tokens)

        logger.info(
            "Context built: %d -> %d messages, %d -> %d tokens (%.1f%% reduction), "
            "pinned=%d, summary=%s, cache=%s",
            result.original_message_count,
            result.final_message_count,
            result.original_tokens,
            result.final_tokens,
            result.compression_ratio * 100,
            len(result.pinned_indices),
            "yes" if result.summary else "no",
            result.cache_provider if result.cache_applied else "no",
        )

        return result

    def _detect_and_pin_messages(self, messages: list[Message]) -> list[int]:
        """检测并固定关键消息"""
        pinned: list[int] = []
        total_messages = len(messages)

        for i, msg in enumerate(messages):
            # 使用 KeyMessageDetector 检测关键消息
            result = self.key_detector.detect(
                message=msg,
                index=i,
                total_messages=total_messages,
            )
            if result.should_pin:
                pinned.append(i)
                # 使用消息内容 hash 作为 ID（简单实现）
                msg_id = str(hash(msg.content or ""))[:16]
                self._pinned_message_ids.add(msg_id)
                logger.debug(
                    "Pinned message %d: types=%s, confidence=%.2f",
                    i,
                    [t.value for t in result.types],
                    result.confidence,
                )

        return pinned

    def _update_plan_tracking(self, messages: list[Message]) -> None:
        """从消息中更新计划追踪"""
        # 简单实现：从最新的 user 消息中提取任务
        for msg in reversed(messages):
            if msg.role == MessageRole.USER and msg.content:
                content = msg.content

                # 检测任务定义模式
                task_indicators = ["任务是", "我需要", "请帮我", "目标是"]
                for indicator in task_indicators:
                    if indicator in content:
                        # 更新计划
                        self.plan_tracker.set_plan(content[:200], [])  # 截取前200字符，初始无步骤
                        break

                # 检测子任务完成
                completion_indicators = ["完成了", "搞定了", "下一步"]
                for indicator in completion_indicators:
                    if indicator in content:
                        # 标记当前子任务完成
                        active_tasks = self.plan_tracker.get_active_sub_tasks()
                        if active_tasks:
                            self.plan_tracker.update_sub_task_status(
                                active_tasks[0].id, "completed"
                            )
                        break

                break  # 只处理最新的用户消息

    def _build_system_content(
        self,
        base_prompt: str,
        recalled_memories: list[dict[str, Any]] | None = None,
        tools_description: str | None = None,
        plan_summary: str | None = None,
    ) -> str:
        """构建完整的系统提示词"""
        parts = [base_prompt]

        # 添加计划摘要
        if plan_summary and plan_summary != "当前没有明确的计划或子任务。":
            parts.append(f"\n\n## 当前任务进度\n{plan_summary}")

        # 添加记忆
        if recalled_memories:
            memory_text = "\n".join(f"- {m.get('content', '')}" for m in recalled_memories[:5])
            parts.append(f"\n\n## 相关记忆\n{memory_text}")

        # 添加工具描述
        if tools_description:
            parts.append(f"\n\n## 可用工具\n{tools_description}")

        return "".join(parts)

    def _simple_trim(self, messages: list[Message]) -> list[Message]:
        """简单裁剪（降级方案）"""
        if not messages:
            return []

        trimmed: list[Message] = []
        total_tokens = 0

        for msg in reversed(messages):
            msg_tokens = count_tokens(msg.content or "")
            if total_tokens + msg_tokens > self.history_budget:
                break
            trimmed.insert(0, msg)
            total_tokens += msg_tokens

        return trimmed

    def _format_message(self, msg: Message) -> dict[str, Any]:
        """格式化消息为 LLM API 格式"""
        formatted: dict[str, Any] = {
            "role": msg.role.value if isinstance(msg.role, MessageRole) else str(msg.role),
            "content": msg.content or "",
        }

        # 处理工具调用
        if msg.tool_calls:
            formatted["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in msg.tool_calls
            ]

        # 处理工具结果
        if msg.role == MessageRole.TOOL and msg.tool_call_id:
            formatted["tool_call_id"] = msg.tool_call_id

        return formatted

    def get_stats(self) -> dict[str, Any]:
        """获取管理器统计信息"""
        cache_stats = self.cache_manager.get_cache_stats()

        return {
            "config": {
                "max_context_tokens": self.config.max_context_tokens,
                "compression_enabled": self.config.compression_enabled,
                "cache_enabled": self.config.cache_enabled,
                "plan_tracking_enabled": self.config.plan_tracking_enabled,
            },
            "pinned_messages": len(self._pinned_message_ids),
            "current_plan": self.plan_tracker.current_plan,
            "active_sub_tasks": len(self.plan_tracker.get_active_sub_tasks()),
            "cache_stats": cache_stats,
        }

    def reset(self) -> None:
        """重置管理器状态"""
        self._pinned_message_ids.clear()
        self.plan_tracker.reset_plan()
        self.cache_manager.reset_stats()
        logger.info("SmartContextManager reset")


# 全局实例（可选）
_smart_context_manager: SmartContextManager | None = None


def get_smart_context_manager(llm_gateway: "LLMGateway") -> SmartContextManager:
    """获取全局智能上下文管理器"""
    global _smart_context_manager
    if _smart_context_manager is None:
        _smart_context_manager = SmartContextManager(llm_gateway)
    return _smart_context_manager
