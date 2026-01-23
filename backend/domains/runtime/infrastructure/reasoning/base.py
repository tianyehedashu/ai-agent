"""
推理模式基类

定义所有推理模式的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any

from shared.types import AgentState, Message, ToolCall


class ReasoningResult:
    """推理结果"""

    def __init__(
        self,
        thought: str,
        action: ToolCall | None = None,
        plan: list[str] | None = None,
        confidence: float = 1.0,
    ) -> None:
        self.thought = thought
        self.action = action
        self.plan = plan
        self.confidence = confidence


class BaseReasoningMode(ABC):
    """
    推理模式基类

    所有推理模式都应继承此类并实现推理逻辑
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    async def reason(
        self,
        state: AgentState,
        context: list[Message],
        available_tools: list[str],
    ) -> ReasoningResult:
        """
        执行推理

        Args:
            state: 当前 Agent 状态
            context: 上下文消息
            available_tools: 可用工具列表

        Returns:
            ReasoningResult: 推理结果
        """
        ...

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取该推理模式的系统提示词

        Returns:
            str: 系统提示词
        """
        ...
