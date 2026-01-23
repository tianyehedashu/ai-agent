"""
执行环境配置集成测试

测试 ExecutionConfig 与 ToolRegistry 的集成
"""

import pytest

from domains.agent.infrastructure.tools.registry import ConfiguredToolRegistry
from libs.config.execution_config import ExecutionConfig, HITLConfig, ToolsConfig
from libs.config.service import (
    ExecutionConfigService,
    get_execution_config_service,
    reset_execution_config_service,
)
from libs.config.sources.toml_source import AgentTomlSource, TomlConfigSource


class TestExecutionConfigServiceIntegration:
    """ExecutionConfigService 集成测试"""

    def test_list_real_templates(self):
        """测试: 列出真实的环境模板"""
        reset_execution_config_service()
        service = get_execution_config_service()

        templates = service.list_templates()

        # 验证能获取模板列表（可能为空）
        assert isinstance(templates, list)


class TestConfiguredToolRegistryIntegration:
    """ConfiguredToolRegistry 集成测试"""

    def test_registry_loads_builtin_tools(self):
        """测试: 加载内置工具"""
        config = ExecutionConfig()
        registry = ConfiguredToolRegistry(config)

        tools = registry.list_all()

        # 应该加载了内置工具
        assert len(tools) > 0

    def test_registry_filters_by_enabled_list(self):
        """测试: 根据启用列表过滤工具"""
        # 只启用 read_file
        config = ExecutionConfig(
            tools=ToolsConfig(enabled=["read_file"]),
        )
        registry = ConfiguredToolRegistry(config)

        # 只有 read_file 可用
        assert registry.get("read_file") is not None
        # 其他工具不可用
        assert registry.get("write_file") is None

    def test_registry_respects_disabled_list(self):
        """测试: 禁用列表生效（需要同时指定 enabled）"""
        # 只有当 enabled 非空时，disabled 才会过滤
        all_tools = ConfiguredToolRegistry(ExecutionConfig()).list_all()
        tool_names = [t.name for t in all_tools]

        config = ExecutionConfig(
            tools=ToolsConfig(
                enabled=tool_names,  # 先启用所有工具
                disabled=["run_shell"],  # 再禁用特定工具
            ),
        )
        registry = ConfiguredToolRegistry(config)

        # run_shell 被禁用
        assert registry.get("run_shell") is None

    @pytest.mark.asyncio
    async def test_execute_tool_with_config(self):
        """测试: 使用配置执行工具"""
        config = ExecutionConfig()
        registry = ConfiguredToolRegistry(config)

        # 如果 read_file 工具存在，测试执行
        if registry.get("read_file"):
            result = await registry.execute("read_file", path="README.md")
            # 验证返回了结果（成功或失败都有结果）
            assert result is not None
            assert hasattr(result, "success")


class TestExecutionConfigServiceSingleton:
    """ExecutionConfigService 单例测试"""

    def teardown_method(self):
        """每个测试后重置单例"""
        reset_execution_config_service()

    def test_singleton_pattern(self):
        """测试: ExecutionConfigService 单例模式"""
        service1 = get_execution_config_service()
        service2 = get_execution_config_service()

        assert service1 is service2

    def test_service_can_load_for_any_agent(self, tmp_path):
        """测试: 服务可以为任意 Agent 加载配置"""
        # 创建简单的测试配置
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "environments").mkdir()
        (config_dir / "execution.toml").write_text(
            """
[sandbox]
mode = "docker"
timeout_seconds = 30
""",
            encoding="utf-8",
        )

        service = ExecutionConfigService(
            system_source=TomlConfigSource(config_dir),
            template_source=TomlConfigSource(config_dir / "environments"),
            agent_source=AgentTomlSource(tmp_path / "agents"),
        )

        # 即使 Agent 不存在，也应该返回默认配置
        config = service.load_for_agent("non-existent-agent-12345")

        assert config is not None
        assert config.sandbox is not None
        assert config.tools is not None


class TestExecutionConfigServiceFeatures:
    """ExecutionConfigService 功能测试"""

    def test_clear_cache(self, tmp_path):
        """测试: 清理缓存功能"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "environments").mkdir()
        (config_dir / "execution.toml").write_text(
            "[sandbox]\nmode = 'docker'\n",
            encoding="utf-8",
        )

        service = ExecutionConfigService(
            system_source=TomlConfigSource(config_dir),
            template_source=TomlConfigSource(config_dir / "environments"),
            agent_source=AgentTomlSource(tmp_path / "agents"),
        )

        # 首次加载
        config1 = service.load_for_agent("test")
        assert config1.sandbox.mode.value == "docker"

        # 修改配置文件
        (config_dir / "execution.toml").write_text(
            "[sandbox]\nmode = 'local'\n",
            encoding="utf-8",
        )

        # 未清理缓存，仍返回旧值
        config2 = service.load_for_agent("test")
        assert config2.sandbox.mode.value == "docker"

        # 清理缓存后，返回新值
        service.clear_cache()
        config3 = service.load_for_agent("test")
        assert config3.sandbox.mode.value == "local"

    def test_load_with_validation(self, tmp_path):
        """测试: 加载时验证配置"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "environments").mkdir()
        # 创建一个无效配置（docker 模式但没有 image）
        (config_dir / "execution.toml").write_text(
            """
[sandbox]
mode = "docker"

[sandbox.docker]
image = ""
""",
            encoding="utf-8",
        )

        service = ExecutionConfigService(
            system_source=TomlConfigSource(config_dir),
            template_source=TomlConfigSource(config_dir / "environments"),
            agent_source=AgentTomlSource(tmp_path / "agents"),
        )

        # 不验证时正常加载
        config = service.load_for_agent("test", validate=False)
        assert config is not None

        # 验证时抛出异常
        with pytest.raises(ValueError, match="Docker mode requires"):
            service.load_for_agent("test", validate=True)

    def test_get_json_schema(self):
        """测试: 获取 JSON Schema"""
        schema = ExecutionConfigService.get_json_schema()

        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "sandbox" in schema["properties"]
        assert "tools" in schema["properties"]
        assert "mcp" in schema["properties"]


class TestToolConfirmationIntegration:
    """工具确认策略集成测试"""

    def test_dangerous_tools_require_confirmation(self):
        """测试: 危险工具需要确认"""
        config = ExecutionConfig(
            tools=ToolsConfig(require_confirmation=["run_shell", "delete_file"]),
        )
        registry = ConfiguredToolRegistry(config)

        assert registry.requires_confirmation("run_shell") is True
        assert registry.requires_confirmation("delete_file") is True
        assert registry.requires_confirmation("read_file") is False

    def test_auto_approve_overrides_confirmation(self):
        """测试: 自动批准模式覆盖确认要求"""
        config = ExecutionConfig(
            tools=ToolsConfig(
                require_confirmation=["read_file"],
                auto_approve_patterns=["read_*"],
            ),
        )
        registry = ConfiguredToolRegistry(config)

        # read_file 匹配 auto_approve，不需要确认
        assert registry.requires_confirmation("read_file") is False

    def test_hitl_config_merges_with_tools_config(self):
        """测试: HITL 配置与工具配置合并"""
        config = ExecutionConfig(
            tools=ToolsConfig(require_confirmation=["write_file"]),
            hitl=HITLConfig(require_confirmation=["run_shell"]),
        )
        registry = ConfiguredToolRegistry(config)

        # 两个配置都应该生效
        assert registry.requires_confirmation("write_file") is True
        assert registry.requires_confirmation("run_shell") is True
