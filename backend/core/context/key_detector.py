"""
Key Message Detector - 关键消息检测器

基于最新研究（SimpleMem, PAACE）实现关键消息检测：
1. 任务定义检测 - 识别用户的任务目标和约束
2. 决策点检测 - 识别重要的决策和结论
3. 代码任务特殊处理 - 文件结构、需求、错误等

参考论文：
- PAACE: Plan-Aware Automated Agent Context Engineering (2025)
- SimpleMem: Efficient Lifelong Memory for LLM Agents (2026)
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any

from core.types import Message, MessageRole
from utils.logging import get_logger

logger = get_logger(__name__)


class KeyMessageType(Enum):
    """关键消息类型"""

    TASK_DEFINITION = "task_definition"  # 任务定义
    USER_CONSTRAINT = "constraint"  # 用户约束
    USER_PREFERENCE = "preference"  # 用户偏好
    DECISION_POINT = "decision"  # 决策点
    CONCLUSION = "conclusion"  # 结论
    ERROR_REPORT = "error"  # 错误报告
    CODE_STRUCTURE = "code_structure"  # 代码结构
    REQUIREMENT = "requirement"  # 需求说明
    PLAN_MILESTONE = "milestone"  # 计划里程碑


@dataclass
class KeyMessageDetectorConfig:
    """检测器配置"""

    # 任务定义关键词
    task_keywords: list[str] = field(
        default_factory=lambda: [
            "帮我",
            "请",
            "需要",
            "想要",
            "目标是",
            "任务是",
            "实现",
            "创建",
            "开发",
            "构建",
            "设计",
            "修改",
            "修复",
            "优化",
            "help me",
            "please",
            "I want",
            "I need",
            "goal is",
            "task is",
            "implement",
            "create",
            "develop",
            "build",
            "design",
            "modify",
            "fix",
            "optimize",
        ]
    )

    # 约束/偏好关键词
    constraint_keywords: list[str] = field(
        default_factory=lambda: [
            "必须",
            "一定要",
            "不要",
            "不能",
            "要求",
            "约束",
            "限制",
            "偏好",
            "喜欢",
            "prefer",
            "must",
            "should",
            "don't",
            "cannot",
            "constraint",
            "requirement",
            "prefer",
        ]
    )

    # 决策/结论关键词
    decision_keywords: list[str] = field(
        default_factory=lambda: [
            "决定",
            "确定",
            "选择",
            "采用",
            "使用",
            "结论",
            "总结",
            "最终",
            "方案",
            "decided",
            "choose",
            "adopt",
            "conclusion",
            "finally",
            "solution",
        ]
    )

    # 代码相关关键词
    code_keywords: list[str] = field(
        default_factory=lambda: [
            "文件",
            "目录",
            "结构",
            "代码",
            "函数",
            "类",
            "模块",
            "API",
            "接口",
            "测试",
            "错误",
            "bug",
            "file",
            "directory",
            "structure",
            "code",
            "function",
            "class",
            "module",
            "interface",
            "test",
            "error",
        ]
    )

    # 首轮对话保护
    protect_first_n_turns: int = 2

    # 最小内容长度（太短的可能不是关键消息）
    min_content_length: int = 20


@dataclass
class DetectionResult:
    """检测结果"""

    is_key_message: bool
    types: list[KeyMessageType]
    confidence: float  # 0.0 - 1.0
    reasons: list[str]
    should_pin: bool  # 是否应该固定（永不删除）


class KeyMessageDetector:
    """
    关键消息检测器

    负责识别对话中的关键消息，包括：
    1. 任务定义和目标
    2. 用户约束和偏好
    3. 重要决策点
    4. 代码任务相关信息

    这些关键消息应该被"固定"在上下文中，不被压缩或删除。
    """

    def __init__(self, config: KeyMessageDetectorConfig | None = None) -> None:
        self.config = config or KeyMessageDetectorConfig()

    def detect(
        self,
        message: Message,
        index: int,
        total_messages: int,
        context: dict[str, Any] | None = None,
    ) -> DetectionResult:
        """
        检测消息是否为关键消息

        Args:
            message: 消息对象
            index: 消息在对话中的位置
            total_messages: 对话总消息数
            context: 额外上下文（如任务类型）

        Returns:
            检测结果
        """
        types: list[KeyMessageType] = []
        reasons: list[str] = []
        confidence = 0.0

        content = message.content or ""
        content_lower = content.lower()

        # 执行各项检测
        confidence += self._detect_position(message, index, types, reasons)
        confidence += self._detect_task_keywords(message, content_lower, types, reasons)
        confidence += self._detect_constraints_preferences(content, content_lower, types, reasons)
        confidence += self._detect_decision_points(message, content_lower, types, reasons)
        confidence += self._detect_code_context(context, content, content_lower, types, reasons)
        confidence += self._detect_content_features(content, reasons)

        # 长度惩罚
        if len(content) < self.config.min_content_length:
            confidence *= 0.5

        # 确保置信度在 [0, 1] 范围内
        confidence = min(1.0, max(0.0, confidence))

        # 判断是否为关键消息
        is_key = len(types) > 0 and confidence >= 0.3

        # 判断是否应该固定（永不删除）
        should_pin = (
            KeyMessageType.TASK_DEFINITION in types
            or KeyMessageType.USER_CONSTRAINT in types
            or KeyMessageType.REQUIREMENT in types
            or (KeyMessageType.CODE_STRUCTURE in types and index < 10)
        )

        return DetectionResult(
            is_key_message=is_key,
            types=types,
            confidence=confidence,
            reasons=reasons,
            should_pin=should_pin,
        )

    def _detect_position(
        self, message: Message, index: int, types: list[KeyMessageType], reasons: list[str]
    ) -> float:
        """检测位置相关的重要性"""
        if index < self.config.protect_first_n_turns * 2 and message.role == MessageRole.USER:
            types.append(KeyMessageType.TASK_DEFINITION)
            reasons.append(f"首轮用户消息（位置 {index}）")
            return 0.3
        return 0.0

    def _detect_task_keywords(
        self,
        message: Message,
        content_lower: str,
        types: list[KeyMessageType],
        reasons: list[str],
    ) -> float:
        """检测任务定义关键词"""
        task_matches = self._count_keyword_matches(content_lower, self.config.task_keywords)
        if task_matches > 0 and message.role == MessageRole.USER:
            types.append(KeyMessageType.TASK_DEFINITION)
            reasons.append(f"包含任务关键词（{task_matches} 个）")
            return min(0.3, task_matches * 0.1)
        return 0.0

    def _detect_constraints_preferences(
        self,
        content: str,
        content_lower: str,
        types: list[KeyMessageType],
        reasons: list[str],
    ) -> float:
        """检测约束/偏好"""
        constraint_matches = self._count_keyword_matches(
            content_lower, self.config.constraint_keywords
        )
        if constraint_matches > 0:
            if "不" in content or "必须" in content or "don't" in content_lower:
                types.append(KeyMessageType.USER_CONSTRAINT)
                reasons.append("包含约束条件")
            else:
                types.append(KeyMessageType.USER_PREFERENCE)
                reasons.append("包含用户偏好")
            return min(0.25, constraint_matches * 0.1)
        return 0.0

    def _detect_decision_points(
        self,
        message: Message,
        content_lower: str,
        types: list[KeyMessageType],
        reasons: list[str],
    ) -> float:
        """检测决策点"""
        decision_matches = self._count_keyword_matches(content_lower, self.config.decision_keywords)
        if decision_matches > 0 and message.role == MessageRole.ASSISTANT:
            types.append(KeyMessageType.DECISION_POINT)
            reasons.append("包含决策/结论")
            return min(0.2, decision_matches * 0.1)
        return 0.0

    def _detect_code_context(
        self,
        context: dict[str, Any] | None,
        content: str,
        content_lower: str,
        types: list[KeyMessageType],
        reasons: list[str],
    ) -> float:
        """检测代码相关上下文"""
        if not context or context.get("task_type") != "code":
            return 0.0

        code_matches = self._count_keyword_matches(content_lower, self.config.code_keywords)
        if code_matches == 0:
            return 0.0

        # 检测具体类型
        if "结构" in content or "structure" in content_lower:
            types.append(KeyMessageType.CODE_STRUCTURE)
            reasons.append("代码结构说明")
        elif "错误" in content or "error" in content_lower or "bug" in content_lower:
            types.append(KeyMessageType.ERROR_REPORT)
            reasons.append("错误报告")
        elif "需求" in content or "requirement" in content_lower:
            types.append(KeyMessageType.REQUIREMENT)
            reasons.append("需求说明")

        return min(0.2, code_matches * 0.05)

    def _detect_content_features(self, content: str, reasons: list[str]) -> float:
        """检测内容特征（代码块、列表等）"""
        score = 0.0
        if "```" in content:
            score += 0.15
            reasons.append("包含代码块")
        if re.search(r"^\s*[-*\d]+[.)]\s", content, re.MULTILINE):
            score += 0.1
            reasons.append("包含列表")
        return score

    def _count_keyword_matches(self, content: str, keywords: list[str]) -> int:
        """计算关键词匹配数"""
        count = 0
        for keyword in keywords:
            if keyword.lower() in content:
                count += 1
        return count

    def detect_batch(
        self,
        messages: list[Message],
        context: dict[str, Any] | None = None,
    ) -> list[DetectionResult]:
        """
        批量检测消息

        Args:
            messages: 消息列表
            context: 额外上下文

        Returns:
            检测结果列表
        """
        total = len(messages)
        return [self.detect(msg, i, total, context) for i, msg in enumerate(messages)]

    def get_pinned_indices(
        self,
        messages: list[Message],
        context: dict[str, Any] | None = None,
    ) -> list[int]:
        """
        获取应该被固定的消息索引

        Args:
            messages: 消息列表
            context: 额外上下文

        Returns:
            应该固定的消息索引列表
        """
        results = self.detect_batch(messages, context)
        return [i for i, r in enumerate(results) if r.should_pin]

    def extract_task_definition(
        self,
        messages: list[Message],
    ) -> str | None:
        """
        从消息中提取任务定义

        Args:
            messages: 消息列表

        Returns:
            任务定义文本，如果未找到则返回 None
        """
        results = self.detect_batch(messages)

        for i, result in enumerate(results):
            if KeyMessageType.TASK_DEFINITION in result.types:
                return messages[i].content

        return None


# 全局检测器实例
_key_detector: KeyMessageDetector | None = None


def get_key_detector() -> KeyMessageDetector:
    """获取全局关键消息检测器"""
    global _key_detector
    if _key_detector is None:
        _key_detector = KeyMessageDetector()
    return _key_detector
