"""
Agent Engine - Agent 执行引擎实现

核心执行循环 (Main Loop):
1. 构建上下文
2. 调用 LLM
3. 解析响应 (文本/工具调用)
4. 执行工具
5. 检查终止条件
6. 循环或结束
"""

from collections.abc import AsyncGenerator
import time
from typing import Any

from core.context.manager import ContextManager
from core.engine.checkpointer import Checkpointer
from core.llm.gateway import LLMGateway
from core.types import (
    AgentConfig,
    AgentEvent,
    AgentState,
    EventType,
    Message,
    MessageRole,
    TerminationCondition,
    TerminationReason,
    ToolCall,
    ToolResult,
)
from tools.registry import ToolRegistry
from utils.logging import get_logger

logger = get_logger(__name__)


class AgentEngine:
    """
    Agent 执行引擎

    实现 ReAct 模式的核心执行循环
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_gateway: LLMGateway | None = None,
        tool_registry: ToolRegistry | None = None,
        checkpointer: Checkpointer | None = None,
    ) -> None:
        self.config = config
        self.llm = llm_gateway or LLMGateway()
        self.tools = tool_registry or ToolRegistry()
        self.checkpointer = checkpointer

        # 上下文管理
        self.context_manager = ContextManager(config)

        # 终止条件
        self.termination = TerminationCondition(
            max_iterations=config.max_iterations,
            max_tokens=100000,
            timeout_seconds=600,
        )

    async def run(
        self,
        session_id: str,
        user_message: str,
        initial_state: AgentState | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        执行 Agent 主循环

        Args:
            session_id: 会话 ID
            user_message: 用户消息
            initial_state: 初始状态 (用于恢复)

        Yields:
            AgentEvent: 执行事件流
        """
        # 初始化状态
        state = initial_state or AgentState(
            session_id=session_id,
            messages=[],
            iteration=0,
        )

        # 添加用户消息
        user_msg = Message(
            role=MessageRole.USER,
            content=user_message,
        )
        state.messages.append(user_msg.model_dump())

        # 记录开始时间
        start_time = time.time()

        try:
            # 主执行循环
            while not state.completed:
                state.iteration += 1

                # 检查终止条件
                termination_reason = self._check_termination(state, start_time)
                if termination_reason:
                    yield AgentEvent(
                        type=EventType.TERMINATED,
                        data={
                            "reason": termination_reason.value,
                            "iteration": state.iteration,
                            "total_tokens": state.total_tokens,
                        },
                    )
                    state.completed = True
                    state.status = "completed"
                    break

                # 发送思考事件
                yield AgentEvent(
                    type=EventType.THINKING,
                    data={
                        "iteration": state.iteration,
                        "status": "processing",
                    },
                )

                # 构建上下文
                messages = [Message.model_validate(m) for m in state.messages]
                context = self.context_manager.build_context(messages)

                # 获取工具定义
                tools = self.tools.to_openai_tools(self.config.tools) if self.config.tools else None

                # 调用 LLM
                response = await self.llm.chat(
                    messages=context,
                    model=self.config.model,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    tools=tools,
                )

                # 更新 token 计数
                if response.usage:
                    state.total_tokens += response.usage.get("total_tokens", 0)

                # 处理 LLM 响应
                if response.tool_calls:
                    # 有工具调用
                    assistant_msg = Message(
                        role=MessageRole.ASSISTANT,
                        tool_calls=response.tool_calls,
                    )
                    state.messages.append(assistant_msg.model_dump())

                    # 执行工具
                    for tool_call in response.tool_calls:
                        # 检查是否需要人工确认
                        if self._needs_human_approval(tool_call):
                            state.pending_tool_call = tool_call.model_dump()
                            state.status = "paused"

                            # 保存检查点
                            checkpoint_id = await self._save_checkpoint(state)

                            yield AgentEvent(
                                type=EventType.INTERRUPT,
                                data={
                                    "checkpoint_id": checkpoint_id,
                                    "pending_action": tool_call.model_dump(),
                                    "reason": "需要人工确认",
                                },
                            )
                            return

                        # 发送工具调用事件
                        yield AgentEvent(
                            type=EventType.TOOL_CALL,
                            data=tool_call.model_dump(),
                        )

                        # 执行工具
                        result = await self._execute_tool(tool_call)

                        # 发送工具结果事件
                        yield AgentEvent(
                            type=EventType.TOOL_RESULT,
                            data=result.model_dump(),
                        )

                        # 添加工具结果消息
                        tool_msg = Message(
                            role=MessageRole.TOOL,
                            content=(result.output if result.success else f"Error: {result.error}"),
                            tool_call_id=tool_call.id,
                        )
                        state.messages.append(tool_msg.model_dump())

                elif response.content:
                    # 纯文本响应
                    assistant_msg = Message(
                        role=MessageRole.ASSISTANT,
                        content=response.content,
                    )
                    state.messages.append(assistant_msg.model_dump())

                    # 发送文本事件
                    yield AgentEvent(
                        type=EventType.TEXT,
                        data={"content": response.content},
                    )

                    # 检查是否完成
                    if response.finish_reason == "stop":
                        state.completed = True
                        state.status = "completed"

                # 保存检查点
                if self.checkpointer and state.iteration % self.config.checkpoint_interval == 0:
                    await self._save_checkpoint(state)

            # 完成事件
            yield AgentEvent(
                type=EventType.DONE,
                data={
                    "iterations": state.iteration,
                    "total_tokens": state.total_tokens,
                    "final_message": state.messages[-1] if state.messages else None,
                },
            )

        except Exception as e:
            logger.exception("Agent execution error: %s", e)
            yield AgentEvent(
                type=EventType.ERROR,
                data={"error": str(e)},
            )

    async def resume(
        self,
        checkpoint_id: str,
        action: str,
        modified_args: dict[str, Any] | None = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        从中断点恢复执行

        Args:
            checkpoint_id: 检查点 ID
            action: 用户操作 (approve/reject/modify)
            modified_args: 修改后的参数 (当 action=modify 时)

        Yields:
            AgentEvent: 执行事件流
        """
        if not self.checkpointer:
            yield AgentEvent(
                type=EventType.ERROR,
                data={"error": "Checkpointer not configured"},
            )
            return

        # 加载检查点
        state = await self.checkpointer.load(checkpoint_id)

        if action == "reject":
            # 用户拒绝
            state.completed = True
            state.status = "completed"
            yield AgentEvent(
                type=EventType.DONE,
                data={
                    "iterations": state.iteration,
                    "total_tokens": state.total_tokens,
                    "rejected": True,
                },
            )
            return

        # 获取待执行的工具调用
        if not state.pending_tool_call:
            yield AgentEvent(
                type=EventType.ERROR,
                data={"error": "No pending tool call"},
            )
            return

        tool_call = ToolCall.model_validate(state.pending_tool_call)

        # 如果用户修改了参数
        if action == "modify" and modified_args:
            tool_call = ToolCall(
                id=tool_call.id,
                name=tool_call.name,
                arguments=modified_args,
            )

        # 发送工具调用事件
        yield AgentEvent(
            type=EventType.TOOL_CALL,
            data=tool_call.model_dump(),
        )

        # 执行工具
        result = await self._execute_tool(tool_call)

        # 发送工具结果事件
        yield AgentEvent(
            type=EventType.TOOL_RESULT,
            data=result.model_dump(),
        )

        # 添加工具结果消息
        tool_msg = Message(
            role=MessageRole.TOOL,
            content=result.output if result.success else f"Error: {result.error}",
            tool_call_id=tool_call.id,
        )
        state.messages.append(tool_msg.model_dump())

        # 清除待执行的工具调用
        state.pending_tool_call = None
        state.status = "running"

        # 继续执行
        async for event in self.run(
            session_id=state.session_id,
            user_message="",  # 空消息，使用现有状态
            initial_state=state,
        ):
            yield event

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """执行工具"""
        start_time = time.time()

        try:
            result = await self.tools.execute(
                tool_call.name,
                **tool_call.arguments,
            )
            result.tool_call_id = tool_call.id
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result
        except Exception as e:
            logger.exception("Tool execution failed: %s - %s", tool_call.name, e)
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                output="",
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _check_termination(
        self,
        state: AgentState,
        start_time: float,
    ) -> TerminationReason | None:
        """检查终止条件"""
        # 最大迭代次数
        if state.iteration >= self.termination.max_iterations:
            return TerminationReason.MAX_ITERATIONS

        # Token 预算
        if state.total_tokens >= self.termination.max_tokens:
            return TerminationReason.TOKEN_BUDGET

        # 超时
        elapsed = time.time() - start_time
        if elapsed >= self.termination.timeout_seconds:
            return TerminationReason.TIMEOUT

        return None

    def _needs_human_approval(self, tool_call: ToolCall) -> bool:
        """检查是否需要人工确认"""
        if not self.config.hitl_enabled:
            return False

        return tool_call.name in self.config.hitl_operations

    async def _save_checkpoint(self, state: AgentState) -> str:
        """保存检查点"""
        if not self.checkpointer:
            return ""

        return await self.checkpointer.save(
            session_id=state.session_id,
            step=state.iteration,
            state=state,
        )
