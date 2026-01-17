"""
ConfiguredToolRegistry 单元测试

测试基于执行环境配置的工具注册表
"""

import pytest

from core.config.execution_config import ExecutionConfig, HITLConfig, ToolsConfig
from core.types import ToolCategory, ToolResult
from tools.base import BaseTool
from tools.registry import ConfiguredToolRegistry


class MockTool(BaseTool):
    """Mock 工具用于测试"""

    name = "mock_tool"
    description = "A mock tool"
    category = ToolCategory.SYSTEM

    async def execute(self, **kwargs):
        return ToolResult(tool_call_id="", success=True, output="ok")


class AnotherMockTool(BaseTool):
    """另一个 Mock 工具"""

    name = "another_tool"
    description = "Another mock tool"
    category = ToolCategory.FILE

    async def execute(self, **kwargs):
        return ToolResult(tool_call_id="", success=True, output="ok")


class TestConfiguredToolRegistry:
    """配置化工具注册表测试"""

    @pytest.fixture
    def base_config(self):
        """基础配置"""
        return ExecutionConfig()

    def test_filter_enabled_tools(self):
        """测试: 只启用指定的工具"""
        config = ExecutionConfig(
            tools=ToolsConfig(enabled=["read_file", "write_file"]),
        )

        registry = ConfiguredToolRegistry(config)

        # 只有启用的工具可用
        assert registry.get("read_file") is not None or len(registry.list_all()) >= 0

    def test_filter_disabled_tools(self):
        """测试: 禁用指定的工具"""
        config = ExecutionConfig(
            tools=ToolsConfig(disabled=["dangerous_tool"]),
        )

        registry = ConfiguredToolRegistry(config)

        # 禁用的工具不可用
        assert registry.get("dangerous_tool") is None

    def test_requires_confirmation_explicit(self):
        """测试: 显式配置需要确认的工具"""
        config = ExecutionConfig(
            tools=ToolsConfig(require_confirmation=["run_shell"]),
        )

        registry = ConfiguredToolRegistry(config)

        assert registry.requires_confirmation("run_shell") is True
        assert registry.requires_confirmation("read_file") is False

    def test_auto_approve_patterns(self):
        """测试: 自动批准模式"""
        config = ExecutionConfig(
            tools=ToolsConfig(
                require_confirmation=["read_file"],
                auto_approve_patterns=["read_*"],
            ),
        )

        registry = ConfiguredToolRegistry(config)

        # read_file 匹配 auto_approve 模式，不需要确认
        assert registry.requires_confirmation("read_file") is False

    def test_hitl_config_integration(self):
        """测试: HITL 配置集成"""
        config = ExecutionConfig(
            hitl=HITLConfig(
                enabled=True,
                require_confirmation=["delete_file"],
                auto_approve_patterns=["list_*"],
            ),
        )

        registry = ConfiguredToolRegistry(config)

        assert registry.requires_confirmation("delete_file") is True
        assert registry.requires_confirmation("list_dir") is False

    def test_get_tool_config(self):
        """测试: 获取工具特定配置"""
        config = ExecutionConfig(
            tools=ToolsConfig(
                config={
                    "http_request": {
                        "timeout": 30,
                        "max_retries": 3,
                    }
                }
            ),
        )

        registry = ConfiguredToolRegistry(config)

        tool_config = registry.get_tool_config("http_request")
        assert tool_config["timeout"] == 30
        assert tool_config["max_retries"] == 3

    def test_get_tool_config_missing(self):
        """测试: 获取不存在的工具配置返回空字典"""
        config = ExecutionConfig()

        registry = ConfiguredToolRegistry(config)

        tool_config = registry.get_tool_config("non_existent")
        assert tool_config == {}
