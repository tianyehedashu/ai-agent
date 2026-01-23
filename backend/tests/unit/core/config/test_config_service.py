"""
ExecutionConfigService 单元测试
"""


import pytest

from shared.infrastructure.config.env_resolver import EnvVarResolver
from shared.infrastructure.config.execution_config import ExecutionConfig
from shared.infrastructure.config.service import (
    ExecutionConfigService,
    get_execution_config_service,
    reset_execution_config_service,
)
from shared.infrastructure.config.sources.toml_source import AgentTomlSource, TomlConfigSource


class TestEnvVarResolver:
    """EnvVarResolver 测试"""

    def test_resolve_env_var(self, monkeypatch):
        """测试: 解析环境变量"""
        monkeypatch.setenv("TEST_VAR", "test_value")

        resolver = EnvVarResolver()
        result = resolver.resolve({"key": "${TEST_VAR}"})

        assert result["key"] == "test_value"

    def test_resolve_with_default(self):
        """测试: 使用默认值"""
        resolver = EnvVarResolver()
        result = resolver.resolve({"key": "${NONEXISTENT:default_value}"})

        assert result["key"] == "default_value"

    def test_resolve_nested(self, monkeypatch):
        """测试: 解析嵌套结构"""
        monkeypatch.setenv("NESTED_VAR", "nested_value")

        resolver = EnvVarResolver()
        result = resolver.resolve(
            {
                "level1": {
                    "level2": "${NESTED_VAR}",
                }
            }
        )

        assert result["level1"]["level2"] == "nested_value"

    def test_resolve_list(self, monkeypatch):
        """测试: 解析列表"""
        monkeypatch.setenv("LIST_VAR", "list_value")

        resolver = EnvVarResolver()
        result = resolver.resolve(["${LIST_VAR}", "static"])

        assert result == ["list_value", "static"]

    def test_preserve_unresolved(self):
        """测试: 保留无法解析的变量"""
        resolver = EnvVarResolver()
        result = resolver.resolve({"key": "${NONEXISTENT}"})

        # 无默认值且环境变量不存在时保留原样
        assert result["key"] == "${NONEXISTENT}"


class TestExecutionConfigService:
    """ExecutionConfigService 测试"""

    @pytest.fixture
    def config_dirs(self, tmp_path):
        """创建测试配置目录"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "environments").mkdir()
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        return config_dir, agents_dir

    @pytest.fixture
    def service(self, config_dirs):
        """创建测试服务实例"""
        config_dir, agents_dir = config_dirs

        # 创建系统默认配置
        (config_dir / "execution.toml").write_text(
            """
[sandbox]
mode = "docker"
timeout_seconds = 30

[sandbox.docker]
image = "python:3.11-slim"
""",
            encoding="utf-8",
        )

        return ExecutionConfigService(
            system_source=TomlConfigSource(config_dir),
            template_source=TomlConfigSource(config_dir / "environments"),
            agent_source=AgentTomlSource(agents_dir),
        )

    def test_load_system_default(self, service):
        """测试: 加载系统默认配置"""
        config = service.load_for_agent("any-agent")

        assert config.sandbox.mode.value == "docker"
        assert config.sandbox.timeout_seconds == 30

    def test_load_with_template(self, config_dirs):
        """测试: 加载带模板的配置"""
        config_dir, agents_dir = config_dirs

        # 创建系统默认配置
        (config_dir / "execution.toml").write_text(
            """
[sandbox]
mode = "docker"
timeout_seconds = 30

[sandbox.docker]
image = "python:3.11-slim"
""",
            encoding="utf-8",
        )

        # 创建模板
        (config_dir / "environments" / "python-dev.toml").write_text(
            """
[sandbox]
timeout_seconds = 60

[tools]
enabled = ["run_python"]
""",
            encoding="utf-8",
        )

        # 创建 Agent 配置
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.toml").write_text(
            'extends = "python-dev"\n',
            encoding="utf-8",
        )

        # 创建新的 service 实例（确保模板文件已经存在）
        service = ExecutionConfigService(
            system_source=TomlConfigSource(config_dir),
            template_source=TomlConfigSource(config_dir / "environments"),
            agent_source=AgentTomlSource(agents_dir),
        )

        config = service.load_for_agent("test-agent")

        assert config.sandbox.timeout_seconds == 60
        assert "run_python" in config.tools.enabled

    def test_load_with_runtime_overrides(self, service):
        """测试: 运行时覆盖"""
        config = service.load_for_agent(
            "any-agent",
            runtime_overrides={"sandbox": {"timeout_seconds": 120}},
        )

        assert config.sandbox.timeout_seconds == 120

    def test_validate_invalid_config(self, service):
        """测试: 验证无效配置"""
        config = ExecutionConfig()
        config.sandbox.mode = config.sandbox.mode.DOCKER
        config.sandbox.docker.image = ""  # 无效

        result = service.validate(config)

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_load_with_validation_error(self, service, config_dirs):
        """测试: 加载时验证失败抛出异常"""
        _config_dir, agents_dir = config_dirs

        # 创建无效的 Agent 配置
        agent_dir = agents_dir / "invalid-agent"
        agent_dir.mkdir()
        (agent_dir / "agent.toml").write_text(
            """
[sandbox]
mode = "docker"

[sandbox.docker]
image = ""
""",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Invalid configuration"):
            service.load_for_agent("invalid-agent", validate=True)

    def test_list_templates(self, service, config_dirs):
        """测试: 列出模板"""
        config_dir, _ = config_dirs

        # 创建模板
        (config_dir / "environments" / "template1.toml").write_text(
            """
[metadata]
description = "Template 1"
tags = ["test"]
""",
            encoding="utf-8",
        )

        templates = service.list_templates()

        assert len(templates) >= 1
        assert any(t["name"] == "template1" for t in templates)

    def test_clear_cache(self, service):
        """测试: 清理缓存"""
        # 首次加载（缓存）
        service.load_for_agent("test")
        assert service._system_default is not None

        # 清理缓存
        service.clear_cache()
        assert service._system_default is None
        assert len(service._templates) == 0

    def test_get_json_schema(self):
        """测试: 获取 JSON Schema"""
        schema = ExecutionConfigService.get_json_schema()

        assert "properties" in schema
        assert "sandbox" in schema["properties"]


class TestServiceSingleton:
    """服务单例测试"""

    def teardown_method(self):
        """每个测试后重置单例"""
        reset_execution_config_service()

    def test_singleton_pattern(self, monkeypatch):
        """测试: 单例模式"""
        monkeypatch.setenv("SANDBOX_MODE", "docker")
        reset_execution_config_service()

        service1 = get_execution_config_service()
        service2 = get_execution_config_service()

        assert service1 is service2

    def test_reset_singleton(self, monkeypatch):
        """测试: 重置单例"""
        monkeypatch.setenv("SANDBOX_MODE", "docker")
        reset_execution_config_service()

        service1 = get_execution_config_service()
        reset_execution_config_service()
        service2 = get_execution_config_service()

        assert service1 is not service2
