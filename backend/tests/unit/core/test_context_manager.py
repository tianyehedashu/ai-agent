"""
Context Manager 单元测试

测试上下文管理器的构建、裁剪和预算管理功能
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from domains.runtime.infrastructure.context.manager import ContextManager
from shared.types import AgentConfig, AgentMode, Message, MessageRole


class TestContextManager:
    """上下文管理器单元测试"""

    @pytest.fixture
    def config(self):
        """测试配置"""
        return AgentConfig(
            name="test-agent",
            mode=AgentMode.EXECUTE,
            system_prompt="You are a helpful assistant.",
        )

    @pytest.fixture
    def context_manager(self, config):
        """创建被测对象"""
        return ContextManager(config=config, max_context_tokens=1000)

    @pytest.fixture
    def mock_llm_gateway(self):
        """Mock LLM Gateway"""
        gateway = AsyncMock()
        gateway.chat.return_value = MagicMock(content="Summary of conversation")
        return gateway

    def test_build_context_includes_system_prompt(self, context_manager):
        """测试: 构建的上下文包含系统提示"""
        # Arrange
        messages = []

        # Act
        result = context_manager.build_context(messages)

        # Assert
        assert len(result) >= 1
        assert result[0]["role"] == "system"
        assert "You are a helpful assistant" in result[0]["content"]

    def test_build_context_includes_user_messages(self, context_manager):
        """测试: 构建的上下文包含用户消息"""
        # Arrange
        messages = [
            Message(role=MessageRole.USER, content="Hello world"),
        ]

        # Act
        result = context_manager.build_context(messages)

        # Assert
        user_messages = [m for m in result if m["role"] == "user"]
        assert len(user_messages) >= 1
        assert user_messages[-1]["content"] == "Hello world"

    def test_build_context_includes_memories(self, context_manager):
        """测试: 构建的上下文包含记忆"""
        # Arrange
        messages = []
        memories = ["User likes Python", "User prefers dark mode"]

        # Act
        result = context_manager.build_context(messages, memories=memories)

        # Assert
        system_content = result[0]["content"]
        assert "相关记忆" in system_content
        assert "User likes Python" in system_content
        assert "User prefers dark mode" in system_content

    def test_build_context_includes_tools_context(self, context_manager):
        """测试: 构建的上下文包含工具上下文"""
        # Arrange
        messages = []
        tools_context = "Available tools: read_file, write_file"

        # Act
        result = context_manager.build_context(messages, tools_context=tools_context)

        # Assert
        system_content = result[0]["content"]
        assert "可用工具" in system_content
        assert "read_file" in system_content

    def test_trim_history_respects_budget(self, context_manager):
        """测试: 历史裁剪遵守预算"""
        # Arrange
        # 创建大量消息，超过预算
        messages = [
            Message(role=MessageRole.USER, content=f"Message {i} " * 100) for i in range(50)
        ]

        # Act
        result = context_manager.build_context(messages)

        # Assert
        # 应该被裁剪，消息数应该少于原始数量
        user_messages = [m for m in result if m["role"] == "user"]
        assert len(user_messages) < len(messages)

    def test_trim_history_preserves_recent_messages(self, context_manager):
        """测试: 裁剪保留最近的消息"""
        # Arrange
        messages = [
            Message(role=MessageRole.USER, content="Old message"),
            Message(role=MessageRole.ASSISTANT, content="Old response"),
            Message(role=MessageRole.USER, content="Recent message"),
        ]

        # Act
        result = context_manager.build_context(messages)

        # Assert
        # 最近的消息应该被保留
        user_messages = [m for m in result if m["role"] == "user"]
        assert len(user_messages) > 0
        # 最后一条应该是最近的消息
        assert user_messages[-1]["content"] == "Recent message"

    def test_empty_history_returns_valid_context(self, context_manager):
        """测试: 空历史记录返回有效上下文"""
        # Act
        result = context_manager.build_context([])

        # Assert
        assert isinstance(result, list)
        assert len(result) >= 1  # 至少有 system prompt
        assert result[0]["role"] == "system"

    def test_get_remaining_budget(self, context_manager):
        """测试: 获取剩余预算"""
        # Arrange
        messages = [
            Message(role=MessageRole.USER, content="Test message"),
        ]

        # Act
        budget = context_manager.get_remaining_budget(messages)

        # Assert
        assert budget >= 0
        assert budget < context_manager.max_context_tokens

    def test_should_summarize_when_history_long(self, context_manager):
        """测试: 历史过长时应该摘要"""
        # Arrange
        # 创建大量消息
        messages = [
            Message(role=MessageRole.USER, content=f"Message {i} " * 50) for i in range(100)
        ]

        # Act
        should_summarize = context_manager.should_summarize(messages)

        # Assert
        assert should_summarize is True

    def test_should_not_summarize_when_history_short(self, context_manager):
        """测试: 历史短时不需要摘要"""
        # Arrange
        messages = [
            Message(role=MessageRole.USER, content="Short message"),
        ]

        # Act
        should_summarize = context_manager.should_summarize(messages)

        # Assert
        assert should_summarize is False

    @pytest.mark.asyncio
    async def test_summarize_history(self, context_manager, mock_llm_gateway):
        """测试: 生成对话摘要"""
        # Arrange
        messages = [
            Message(role=MessageRole.USER, content="What is Python?"),
            Message(role=MessageRole.ASSISTANT, content="Python is a programming language."),
        ]

        # Act
        summary = await context_manager.summarize_history(messages, mock_llm_gateway)

        # Assert
        assert isinstance(summary, str)
        assert len(summary) > 0
        mock_llm_gateway.chat.assert_called_once()

    def test_format_message_with_tool_calls(self, context_manager):
        """测试: 格式化包含工具调用的消息"""
        # Arrange
        from shared.types import ToolCall

        message = Message(
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=[
                ToolCall(
                    id="call_123",
                    name="read_file",
                    arguments={"path": "/tmp/test.txt"},
                ),
            ],
        )

        # Act
        formatted = context_manager._format_message(message)

        # Assert
        assert formatted["role"] == "assistant"
        assert "tool_calls" in formatted
        assert len(formatted["tool_calls"]) == 1
        assert formatted["tool_calls"][0]["function"]["name"] == "read_file"

    def test_default_system_prompt_when_none(self):
        """测试: 无系统提示时使用默认提示"""
        # Arrange
        config = AgentConfig(name="test", system_prompt=None)
        manager = ContextManager(config=config)

        # Act
        result = manager.build_context([])

        # Assert
        assert result[0]["role"] == "system"
        assert len(result[0]["content"]) > 0
        assert "AI 助手" in result[0]["content"] or "assistant" in result[0]["content"].lower()
