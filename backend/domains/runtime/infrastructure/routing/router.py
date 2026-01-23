"""
条件路由器

实现确定性路由逻辑，根据 Agent 状态决定下一步操作
"""

from enum import Enum

from shared.types import AgentState


class RouteDecision(str, Enum):
    """路由决策"""

    CONTINUE = "continue"  # 继续推理
    EXECUTE_TOOLS = "execute_tools"  # 执行工具
    WAIT_FOR_HUMAN = "wait_for_human"  # 等待人工确认
    ERROR_HANDLER = "error_handler"  # 错误处理
    FINISH = "finish"  # 任务完成


class StateRouter:
    """
    状态路由器

    根据 Agent 状态进行确定性路由，不依赖 LLM
    """

    def __init__(self) -> None:
        pass

    def route(self, state: AgentState) -> RouteDecision:
        """
        路由决策

        优先级：
        1. 检查是否有待确认的高风险操作
        2. 检查是否有错误
        3. 检查是否有工具调用
        4. 检查是否任务完成
        5. 默认继续推理

        Args:
            state: Agent 状态

        Returns:
            RouteDecision: 路由决策
        """
        # 优先级1: 检查是否有待确认的高风险操作
        if state.pending_tool_call:
            return RouteDecision.WAIT_FOR_HUMAN

        # 优先级2: 检查是否有错误
        if state.status == "error" or state.metadata.get("last_error"):
            return RouteDecision.ERROR_HANDLER

        # 优先级3: 检查是否有待执行的工具调用
        # 注意: AgentState 使用 pending_tool_call (单数)，这里检查消息中的工具调用
        if state.messages and any(
            msg.role.value == "assistant" and msg.tool_calls for msg in state.messages
        ):
            return RouteDecision.EXECUTE_TOOLS

        # 优先级4: 检查是否任务完成
        if state.completed or state.status == "completed":
            return RouteDecision.FINISH

        # 默认: 继续推理
        return RouteDecision.CONTINUE

    def should_interrupt(self, state: AgentState) -> bool:
        """
        判断是否应该中断等待人工确认

        Args:
            state: Agent 状态

        Returns:
            bool: 是否需要中断
        """
        return self.route(state) == RouteDecision.WAIT_FOR_HUMAN
