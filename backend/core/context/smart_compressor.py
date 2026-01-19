"""
Smart Context Compressor - 智能上下文压缩器

解决简单滑动窗口的问题：
1. 丢失重要上下文：早期对话中可能包含重要的决策、用户偏好
2. 缺乏智能选择：没有根据内容重要性来选择保留哪些消息
3. 上下文断裂：直接丢弃消息导致对话不连贯

智能压缩策略（基于最新学术研究 2025-2026）：
1. 首轮保护：保留任务定义和初始上下文
2. 重要性评分：根据内容特征判断消息重要性
3. 关键点保留：保留包含决策、结论的消息
4. 摘要压缩：将早期对话压缩为摘要
5. 最近消息：保留最近 N 条消息确保连贯性

参考论文：
- PAACE: Plan-Aware Automated Agent Context Engineering (arXiv:2512.16970, 2025)
- SimpleMem: Efficient Lifelong Memory for LLM Agents (arXiv:2601.02553, 2026)
- Sculptor: Empowering LLMs with Active Context Management (arXiv:2508.04664, 2025)
- Cognitive Workspace: Active Memory Management (arXiv:2508.13171, 2025)
- AgeMem: Agentic Memory for LLM Agents (2026)
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import TYPE_CHECKING, Any

from core.types import Message, MessageRole
from core.utils.message_formatter import estimate_message_tokens, format_tool_calls
from utils.logging import get_logger
from utils.tokens import count_tokens

if TYPE_CHECKING:
    from core.llm.gateway import LLMGateway

logger = get_logger(__name__)


class MessageImportance(Enum):
    """消息重要性等级"""

    CRITICAL = 5  # 关键消息（任务定义、最终决策）
    HIGH = 4  # 高重要性（重要决策、关键信息）
    MEDIUM = 3  # 中等重要性（正常对话）
    LOW = 2  # 低重要性（简单确认、过渡语）
    TRIVIAL = 1  # 可忽略（寒暄、重复内容）


@dataclass
class ScoredMessage:
    """带评分的消息"""

    message: Message
    importance: MessageImportance
    score: float
    tokens: int
    index: int  # 原始位置
    reasons: list[str] = field(default_factory=list)

    @property
    def is_protected(self) -> bool:
        """是否受保护（不可删除）"""
        return self.importance == MessageImportance.CRITICAL


@dataclass
class CompressionConfig:
    """压缩配置"""

    # Token 预算
    max_history_tokens: int = 80000

    # 保护策略
    protect_first_n_turns: int = 2  # 保护前 N 轮对话（任务定义）
    protect_last_n_messages: int = 6  # 保护最近 N 条消息

    # 摘要配置
    enable_summarization: bool = True
    summarization_threshold: float = 0.7  # 超过预算的 70% 时触发摘要
    max_summary_tokens: int = 500

    # SimpleMem 协同配置
    enable_memory_dedup: bool = True  # 启用记忆去重（降低已在记忆中的消息优先级）
    memory_overlap_penalty: float = 15.0  # 与记忆重叠时的降分值

    # 重要性关键词（用于评分）
    critical_keywords: list[str] = field(
        default_factory=lambda: [
            "决定",
            "确定",
            "最终",
            "结论",
            "总结",
            "关键",
            "重要",
            "必须",
            "请记住",
            "注意",
        ]
    )
    high_importance_keywords: list[str] = field(
        default_factory=lambda: [
            "方案",
            "计划",
            "步骤",
            "原因",
            "因为",
            "所以",
            "建议",
            "推荐",
            "选择",
            "偏好",
        ]
    )


@dataclass
class CompressionResult:
    """压缩结果"""

    messages: list[Message]
    summary: str | None
    original_count: int
    compressed_count: int
    original_tokens: int
    compressed_tokens: int
    dropped_messages: int
    summarized_messages: int

    @property
    def compression_ratio(self) -> float:
        """压缩比"""
        if self.original_tokens == 0:
            return 0.0
        return 1 - (self.compressed_tokens / self.original_tokens)


class SmartContextCompressor:
    """
    智能上下文压缩器

    核心策略：
    1. 首轮保护 - 保留任务定义和初始上下文
    2. 重要性评分 - 根据内容特征判断消息重要性
    3. 摘要压缩 - 将低重要性的早期对话压缩为摘要
    4. 尾部保护 - 保留最近消息确保连贯性
    """

    def __init__(
        self,
        llm_gateway: "LLMGateway | None" = None,
        config: CompressionConfig | None = None,
    ) -> None:
        """
        初始化智能压缩器

        Args:
            llm_gateway: LLM 网关（用于生成摘要）
            config: 压缩配置
        """
        self.llm_gateway = llm_gateway
        self.config = config or CompressionConfig()
        self._summary_cache: dict[str, str] = {}  # 摘要缓存

    async def compress(
        self,
        messages: list[Message],
        budget_tokens: int | None = None,
        recalled_memories: list[str] | None = None,
    ) -> CompressionResult:
        """
        智能压缩消息列表

        Args:
            messages: 原始消息列表
            budget_tokens: Token 预算（可选，默认使用配置）
            recalled_memories: 已召回的记忆内容列表（用于去重优化）

        Returns:
            压缩结果
        """
        if not messages:
            return CompressionResult(
                messages=[],
                summary=None,
                original_count=0,
                compressed_count=0,
                original_tokens=0,
                compressed_tokens=0,
                dropped_messages=0,
                summarized_messages=0,
            )

        budget = budget_tokens or self.config.max_history_tokens

        # 1. 计算原始 Token 数
        original_tokens = sum(self._estimate_tokens(m) for m in messages)

        # 如果未超预算，直接返回
        if original_tokens <= budget:
            return CompressionResult(
                messages=messages,
                summary=None,
                original_count=len(messages),
                compressed_count=len(messages),
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                dropped_messages=0,
                summarized_messages=0,
            )

        # 2. 对所有消息进行重要性评分（考虑已召回的记忆）
        scored_messages = self._score_messages(messages, recalled_memories)

        # 3. 标记保护区域
        self._mark_protected_regions(scored_messages)

        # 4. 决定压缩策略
        summary = None
        summarized_count = 0

        # 检查是否需要摘要
        if self.config.enable_summarization and self.llm_gateway:
            threshold_tokens = int(budget * self.config.summarization_threshold)
            if original_tokens > threshold_tokens:
                # 需要摘要：压缩中间部分
                summary, summarized_count = await self._summarize_middle_section(
                    scored_messages, budget
                )

        # 5. 选择保留的消息
        final_messages, dropped_count = self._select_messages(scored_messages, budget, summary)

        # 6. 构建最终结果
        compressed_tokens = sum(self._estimate_tokens(m) for m in final_messages)
        if summary:
            compressed_tokens += count_tokens(summary)

        return CompressionResult(
            messages=final_messages,
            summary=summary,
            original_count=len(messages),
            compressed_count=len(final_messages),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            dropped_messages=dropped_count,
            summarized_messages=summarized_count,
        )

    def _score_messages(
        self,
        messages: list[Message],
        recalled_memories: list[str] | None = None,
    ) -> list[ScoredMessage]:
        """
        对消息进行重要性评分

        评分因素：
        1. 位置权重（首尾重要）
        2. 内容关键词
        3. 消息类型（工具调用通常重要）
        4. 长度（太短可能是确认语）
        5. 与召回记忆的重叠度（SimpleMem 协同）
        """
        scored = []
        total = len(messages)

        for i, msg in enumerate(messages):
            importance, score, reasons = self._calculate_importance(msg, i, total)

            # SimpleMem 协同：如果消息内容与召回记忆高度重叠，降低优先级
            if recalled_memories and self.config.enable_memory_dedup and msg.content:
                overlap = self._calculate_memory_overlap(msg.content, recalled_memories)
                if overlap > 0.5:  # 超过 50% 重叠
                    penalty = self.config.memory_overlap_penalty * overlap
                    score -= penalty
                    reasons.append(f"记忆重叠({overlap:.0%})")
                    logger.debug(
                        "Message %d overlaps with memory (%.0f%%), score reduced by %.1f",
                        i,
                        overlap * 100,
                        penalty,
                    )

            tokens = self._estimate_tokens(msg)

            scored.append(
                ScoredMessage(
                    message=msg,
                    importance=importance,
                    score=score,
                    tokens=tokens,
                    index=i,
                    reasons=reasons,
                )
            )

        return scored

    def _calculate_memory_overlap(
        self,
        content: str,
        memories: list[str],
    ) -> float:
        """
        计算消息内容与记忆的重叠度

        使用简单的词袋模型计算 Jaccard 相似度。
        如果需要更精确，可以使用向量相似度，但会增加计算成本。

        Args:
            content: 消息内容
            memories: 记忆内容列表

        Returns:
            最高重叠度（0-1）
        """
        if not content or not memories:
            return 0.0

        # 简化处理：使用词袋模型
        content_words = set(content.lower().split())
        if len(content_words) < 3:  # 太短的内容不做去重
            return 0.0

        max_overlap = 0.0
        for memory in memories:
            memory_words = set(memory.lower().split())
            if not memory_words:
                continue

            # Jaccard 相似度
            intersection = len(content_words & memory_words)
            union = len(content_words | memory_words)
            if union > 0:
                overlap = intersection / union
                max_overlap = max(max_overlap, overlap)

        return max_overlap

    def _calculate_importance(
        self, message: Message, index: int, total: int
    ) -> tuple[MessageImportance, float, list[str]]:
        """
        计算单条消息的重要性

        Returns:
            (重要性等级, 综合分数, 原因列表)
        """
        score = 0.0
        reasons = []
        content = message.content or ""
        content_lower = content.lower()

        # 1. 位置权重
        score += self._calculate_position_score(index, total, reasons)
        # 2. 角色和工具权重
        score += self._calculate_role_and_tool_score(message, reasons)
        # 3. 关键词匹配
        score += self._calculate_keyword_score(content_lower, reasons)
        # 4. 内容特征
        score += self._calculate_content_features_score(content, reasons)
        # 5. 长度调整
        score += self._calculate_length_score(content, reasons)
        # 6. 确定重要性等级
        importance = self._score_to_importance(score)

        return importance, score, reasons

    def _calculate_position_score(self, index: int, total: int, reasons: list[str]) -> float:
        """计算位置权重分数"""
        score = 0.0
        if index < 4:  # 前 2 轮
            score += 30
            reasons.append("首轮对话")
        if index >= total - self.config.protect_last_n_messages:
            score += 25
            reasons.append("最近消息")
        return score

    def _calculate_role_and_tool_score(self, message: Message, reasons: list[str]) -> float:
        """计算角色和工具调用权重分数"""
        score = 0.0
        if message.role == MessageRole.USER:
            score += 10
            reasons.append("用户消息")
        elif message.role == MessageRole.ASSISTANT:
            score += 8
        if message.tool_calls:
            score += 20
            reasons.append("包含工具调用")
        if message.tool_call_id:
            score += 15
            reasons.append("工具执行结果")
        return score

    def _calculate_keyword_score(self, content_lower: str, reasons: list[str]) -> float:
        """计算关键词匹配分数"""
        score = 0.0
        for keyword in self.config.critical_keywords:
            if keyword in content_lower:
                score += 15
                reasons.append(f"关键词:{keyword}")
                break
        for keyword in self.config.high_importance_keywords:
            if keyword in content_lower:
                score += 8
                reasons.append(f"重要词:{keyword}")
                break
        return score

    def _calculate_content_features_score(self, content: str, reasons: list[str]) -> float:
        """计算内容特征分数"""
        score = 0.0
        if "```" in content:
            score += 12
            reasons.append("包含代码")
        if re.search(r"^\s*[-*\d]+[.)]\s", content, re.MULTILINE):
            score += 8
            reasons.append("包含列表")
        if "?" in content or "？" in content:
            score += 5
            reasons.append("包含问题")
        return score

    def _calculate_length_score(self, content: str, reasons: list[str]) -> float:
        """计算长度调整分数"""
        score = 0.0
        if len(content) < 20:
            score -= 10
            reasons.append("内容过短")
        elif len(content) > 500:
            score += 5
            reasons.append("详细内容")
        return score

    def _score_to_importance(self, score: float) -> MessageImportance:
        """根据分数确定重要性等级"""
        if score >= 50:
            return MessageImportance.CRITICAL
        if score >= 35:
            return MessageImportance.HIGH
        if score >= 20:
            return MessageImportance.MEDIUM
        if score >= 10:
            return MessageImportance.LOW
        return MessageImportance.TRIVIAL

    def _mark_protected_regions(self, scored_messages: list[ScoredMessage]) -> None:
        """标记受保护的区域"""
        total = len(scored_messages)

        # 保护前 N 轮
        protect_head = self.config.protect_first_n_turns * 2
        for i in range(min(protect_head, total)):
            if scored_messages[i].importance.value < MessageImportance.CRITICAL.value:
                scored_messages[i].importance = MessageImportance.CRITICAL
                scored_messages[i].reasons.append("首轮保护")

        # 保护尾部
        protect_tail = self.config.protect_last_n_messages
        for i in range(max(0, total - protect_tail), total):
            if scored_messages[i].importance.value < MessageImportance.HIGH.value:
                scored_messages[i].importance = MessageImportance.HIGH
                scored_messages[i].reasons.append("尾部保护")

    async def _summarize_middle_section(
        self,
        scored_messages: list[ScoredMessage],
        budget: int,
    ) -> tuple[str | None, int]:
        """
        摘要中间部分的低重要性消息

        Returns:
            (摘要文本, 被摘要的消息数)
        """
        if not self.llm_gateway:
            return None, 0

        # 找出可以被摘要的消息（中间部分的低重要性消息）
        protect_head = self.config.protect_first_n_turns * 2
        protect_tail = self.config.protect_last_n_messages
        total = len(scored_messages)

        # 中间部分
        start_idx = protect_head
        end_idx = total - protect_tail

        if start_idx >= end_idx:
            return None, 0

        # 选择低重要性消息进行摘要
        to_summarize = []
        for sm in scored_messages[start_idx:end_idx]:
            if sm.importance.value <= MessageImportance.MEDIUM.value:
                to_summarize.append(sm)

        if len(to_summarize) < 3:  # 太少不值得摘要
            return None, 0

        # 生成摘要
        summary = await self._generate_summary([sm.message for sm in to_summarize])

        return summary, len(to_summarize)

    async def _generate_summary(self, messages: list[Message]) -> str:
        """生成消息摘要"""
        if not self.llm_gateway:
            return ""

        # 构建摘要请求
        conversation = "\n".join(f"{m.role.value}: {m.content or '[工具调用]'}" for m in messages)

        prompt = f"""请简洁地总结以下对话的关键信息，保留：
1. 重要的决策和结论
2. 用户的偏好和要求
3. 关键的数据或事实

对话内容：
{conversation}

请用一段话（不超过 200 字）输出摘要："""

        try:
            response = await self.llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.max_summary_tokens,
                temperature=0.3,
            )
            return response.content or ""
        except Exception as e:
            logger.error("Failed to generate summary: %s", e)
            return ""

    def _select_messages(
        self,
        scored_messages: list[ScoredMessage],
        budget: int,
        summary: str | None,
    ) -> tuple[list[Message], int]:
        """
        选择要保留的消息

        策略：
        1. 优先保留 CRITICAL 和 HIGH 重要性的消息
        2. 按分数降序选择，直到达到预算
        3. 确保消息顺序正确

        Returns:
            (保留的消息列表, 丢弃的消息数)
        """
        # 计算可用预算（扣除摘要）
        available_budget = budget
        if summary:
            available_budget -= count_tokens(summary) + 50  # 摘要 + 前缀

        # 分离必须保留和可选消息
        must_keep = []
        optional = []

        for sm in scored_messages:
            if sm.is_protected or sm.importance == MessageImportance.HIGH:
                must_keep.append(sm)
            else:
                optional.append(sm)

        # 计算必须保留的 Token 数
        must_keep_tokens = sum(sm.tokens for sm in must_keep)

        # 如果必须保留的已超预算，只保留 CRITICAL
        if must_keep_tokens > available_budget:
            must_keep = [sm for sm in must_keep if sm.is_protected]
            must_keep_tokens = sum(sm.tokens for sm in must_keep)

        # 剩余预算分配给可选消息
        remaining_budget = available_budget - must_keep_tokens

        # 按分数排序可选消息
        optional.sort(key=lambda x: x.score, reverse=True)

        # 选择可选消息
        selected_optional = []
        for sm in optional:
            if sm.tokens <= remaining_budget:
                selected_optional.append(sm)
                remaining_budget -= sm.tokens

        # 合并并按原始位置排序
        all_selected = must_keep + selected_optional
        all_selected.sort(key=lambda x: x.index)

        # 提取消息
        final_messages = [sm.message for sm in all_selected]
        dropped_count = len(scored_messages) - len(final_messages)

        return final_messages, dropped_count

    def _estimate_tokens(self, message: Message) -> int:
        """估算消息 Token 数（复用公共函数）"""
        return estimate_message_tokens(message)

    def build_compressed_context(
        self,
        result: CompressionResult,
    ) -> list[dict[str, Any]]:
        """
        构建压缩后的上下文

        如果有摘要，将其作为系统消息的一部分注入。

        Args:
            result: 压缩结果

        Returns:
            格式化的消息列表
        """
        context: list[dict[str, Any]] = []

        # 如果有摘要，添加为特殊的系统消息
        if result.summary:
            context.append(
                {
                    "role": "system",
                    "content": f"[之前对话摘要]\n{result.summary}",
                }
            )

        # 添加保留的消息（复用公共格式化函数）
        for msg in result.messages:
            formatted: dict[str, Any] = {"role": msg.role.value}

            if msg.content:
                formatted["content"] = msg.content

            if msg.tool_calls:
                formatted["tool_calls"] = format_tool_calls(msg.tool_calls)

            if msg.tool_call_id:
                formatted["tool_call_id"] = msg.tool_call_id

            context.append(formatted)

        return context

    def get_compression_preview(
        self,
        messages: list[Message],
        budget_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        获取压缩预览（不实际执行摘要）

        用于 UI 展示或调试。

        Args:
            messages: 消息列表
            budget_tokens: Token 预算

        Returns:
            预览信息
        """
        budget = budget_tokens or self.config.max_history_tokens
        scored = self._score_messages(messages)
        self._mark_protected_regions(scored)

        # 统计各重要性等级的消息
        importance_counts = {level.name: 0 for level in MessageImportance}
        importance_tokens = {level.name: 0 for level in MessageImportance}

        for sm in scored:
            importance_counts[sm.importance.name] += 1
            importance_tokens[sm.importance.name] += sm.tokens

        total_tokens = sum(sm.tokens for sm in scored)

        return {
            "total_messages": len(messages),
            "total_tokens": total_tokens,
            "budget_tokens": budget,
            "over_budget": total_tokens > budget,
            "needs_compression": total_tokens > budget * self.config.summarization_threshold,
            "importance_distribution": {
                level.name: {
                    "count": importance_counts[level.name],
                    "tokens": importance_tokens[level.name],
                }
                for level in MessageImportance
            },
            "protected_messages": sum(1 for sm in scored if sm.is_protected),
            "message_details": [
                {
                    "index": sm.index,
                    "role": sm.message.role.value,
                    "importance": sm.importance.name,
                    "score": sm.score,
                    "tokens": sm.tokens,
                    "reasons": sm.reasons,
                    "preview": (sm.message.content or "")[:50] + "..."
                    if sm.message.content and len(sm.message.content) > 50
                    else sm.message.content or "[工具调用]",
                }
                for sm in scored
            ],
        }
