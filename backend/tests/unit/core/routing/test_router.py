"""
Routing 单元测试
"""

import pytest

from domains.agent.domain.types import (
    AgentState,
    Message,
    MessageRole,
    ToolCall,
)
from domains.agent.infrastructure.routing.router import RouteDecision, StateRouter


@pytest.mark.unit
class TestStateRouter:
    """State Router 测试"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        return StateRouter()

    def test_route_pending_tool_call(self, router):
        """测试: 有待确认的工具调用时等待人工确认"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
            pending_tool_call={"name": "run_shell", "arguments": {"command": "rm -rf /"}},
        )

        # Act
        decision = router.route(state)

        # Assert
        assert decision == RouteDecision.WAIT_FOR_HUMAN

    def test_route_error_state(self, router):
        """测试: 错误状态路由到错误处理"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
            status="error",
        )

        # Act
        decision = router.route(state)

        # Assert
        assert decision == RouteDecision.ERROR_HANDLER

    def test_route_error_in_metadata(self, router):
        """测试: 元数据中有错误时路由到错误处理"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
            metadata={"last_error": "Something went wrong"},
        )

        # Act
        decision = router.route(state)

        # Assert
        assert decision == RouteDecision.ERROR_HANDLER

    def test_route_tool_calls(self, router):
        """测试: 有工具调用时路由到执行工具"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[
                Message(
                    role=MessageRole.ASSISTANT,
                    content="",
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            name="read_file",
                            arguments={"path": "/tmp/test.txt"},
                        )
                    ],
                )
            ],
            iteration=1,
            total_tokens=0,
        )

        # Act
        decision = router.route(state)

        # Assert
        assert decision == RouteDecision.EXECUTE_TOOLS

    def test_route_completed(self, router):
        """测试: 任务完成时路由到完成"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
            completed=True,
        )

        # Act
        decision = router.route(state)

        # Assert
        assert decision == RouteDecision.FINISH

    def test_route_completed_status(self, router):
        """测试: 状态为 completed 时路由到完成"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
            status="completed",
        )

        # Act
        decision = router.route(state)

        # Assert
        assert decision == RouteDecision.FINISH

    def test_route_continue(self, router):
        """测试: 默认情况继续推理"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
        )

        # Act
        decision = router.route(state)

        # Assert
        assert decision == RouteDecision.CONTINUE

    def test_should_interrupt_true(self, router):
        """测试: 应该中断的情况"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
            pending_tool_call={"name": "run_shell", "arguments": {"command": "rm -rf /"}},
        )

        # Act
        should = router.should_interrupt(state)

        # Assert
        assert should is True

    def test_should_interrupt_false(self, router):
        """测试: 不应该中断的情况"""
        # Arrange
        state = AgentState(
            session_id="test_session",
            messages=[],
            iteration=1,
            total_tokens=0,
        )

        # Act
        should = router.should_interrupt(state)

        # Assert
        assert should is False
