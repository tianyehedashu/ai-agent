"""
Tool Registry 单元测试

测试工具注册、检索和执行功能
"""

import pytest

from core.types import ToolCategory, ToolResult
from tools.base import BaseTool
from tools.registry import ToolRegistry


class MockTool(BaseTool):
    """Mock 工具用于测试"""

    name = "mock_tool"
    description = "A mock tool for testing"
    category = ToolCategory.SYSTEM

    def __init__(self):
        super().__init__()
        self.execute_called = False

    async def execute(self, **kwargs):
        """执行工具"""
        self.execute_called = True
        return ToolResult(
            tool_call_id=kwargs.get("tool_call_id", "test-call"),
            success=True,
            output="Mock result",
        )


class TestToolRegistry:
    """工具注册表测试"""

    @pytest.fixture
    def registry(self):
        """创建注册表实例"""
        return ToolRegistry()

    @pytest.fixture
    def mock_tool(self):
        """创建 Mock 工具"""
        return MockTool()

    def test_register_tool(self, registry, mock_tool):
        """测试: 注册工具"""
        # Act
        registry.register(mock_tool)

        # Assert
        assert registry.get("mock_tool") == mock_tool

    def test_get_tool_exists(self, registry, mock_tool):
        """测试: 获取存在的工具"""
        # Arrange
        registry.register(mock_tool)

        # Act
        tool = registry.get("mock_tool")

        # Assert
        assert tool is not None
        assert tool.name == "mock_tool"

    def test_get_tool_not_exists(self, registry):
        """测试: 获取不存在的工具返回 None"""
        # Act
        tool = registry.get("non_existent_tool")

        # Assert
        assert tool is None

    def test_list_all_tools(self, registry, mock_tool):
        """测试: 列出所有工具"""
        # Arrange
        registry.register(mock_tool)

        # Act
        tools = registry.list_all()

        # Assert
        assert len(tools) > 0
        assert any(t.name == "mock_tool" for t in tools)

    def test_list_by_category(self, registry, mock_tool):
        """测试: 按分类列出工具"""
        # Arrange
        registry.register(mock_tool)

        # Act
        system_tools = registry.list_by_category(ToolCategory.SYSTEM)

        # Assert
        assert len(system_tools) > 0
        assert any(t.name == "mock_tool" for t in system_tools)

    def test_get_tools_for_agent(self, registry, mock_tool):
        """测试: 获取指定工具列表"""
        # Arrange
        registry.register(mock_tool)

        # Act
        tools = registry.get_tools_for_agent(["mock_tool", "non_existent"])

        # Assert
        assert len(tools) == 1
        assert tools[0].name == "mock_tool"

    def test_to_openai_tools(self, registry, mock_tool):
        """测试: 转换为 OpenAI 工具格式"""
        # Arrange
        registry.register(mock_tool)

        # Act
        openai_tools = registry.to_openai_tools(["mock_tool"])

        # Assert
        assert len(openai_tools) == 1
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "mock_tool"

    def test_to_anthropic_tools(self, registry, mock_tool):
        """测试: 转换为 Anthropic 工具格式"""
        # Arrange
        registry.register(mock_tool)

        # Act
        anthropic_tools = registry.to_anthropic_tools(["mock_tool"])

        # Assert
        assert len(anthropic_tools) == 1
        assert anthropic_tools[0]["name"] == "mock_tool"

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, registry, mock_tool):
        """测试: 执行工具成功"""
        # Arrange
        registry.register(mock_tool)

        # Act
        result = await registry.execute("mock_tool", tool_call_id="test-123")

        # Assert
        assert result.success is True
        assert result.output == "Mock result"
        assert mock_tool.execute_called is True

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, registry):
        """测试: 执行不存在的工具"""
        # Act
        result = await registry.execute("non_existent_tool")

        # Assert
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_tool_with_error(self, registry):
        """测试: 工具执行错误处理"""
        # Arrange
        error_tool = MockTool()

        async def failing_execute(**kwargs):
            raise Exception("Tool execution failed")

        error_tool.execute = failing_execute
        registry.register(error_tool)

        # Act
        result = await registry.execute("mock_tool")

        # Assert
        assert result.success is False
        assert "error" in result.error.lower()
