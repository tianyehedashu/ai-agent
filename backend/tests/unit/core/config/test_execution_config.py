"""
ExecutionConfig 单元测试

测试执行环境配置模型和配置合并逻辑
"""

from shared.infrastructure.config.execution_config import (
    ConfigMerger,
    ExecutionConfig,
    HITLConfig,
    SandboxConfig,
    SandboxMode,
    ShellConfig,
    ToolsConfig,
)


class TestExecutionConfig:
    """执行环境配置测试"""

    def test_default_config_creation(self):
        """测试: 创建默认配置"""
        config = ExecutionConfig()

        assert config.sandbox.mode == SandboxMode.DOCKER
        assert config.sandbox.timeout_seconds == 30
        assert config.shell.work_dir == "/workspace"
        assert config.hitl.enabled is True

    def test_config_from_dict(self):
        """测试: 从字典创建配置"""
        data = {
            "sandbox": {"mode": "local", "timeout_seconds": 60},
            "shell": {"work_dir": "/app"},
            "tools": {"enabled": ["read_file", "write_file"]},
        }

        config = ExecutionConfig.model_validate(data)

        assert config.sandbox.mode == SandboxMode.LOCAL
        assert config.sandbox.timeout_seconds == 60
        assert config.shell.work_dir == "/app"
        assert "read_file" in config.tools.enabled


class TestConfigMerger:
    """配置合并器测试"""

    def test_merge_scalar_values(self):
        """测试: 标量值覆盖"""
        base = ExecutionConfig(
            sandbox=SandboxConfig(timeout_seconds=30),
        )
        override = ExecutionConfig(
            sandbox=SandboxConfig(timeout_seconds=60),
        )

        result = ConfigMerger.merge(base, override)

        assert result.sandbox.timeout_seconds == 60

    def test_merge_list_replaces(self):
        """测试: 列表替换（不合并）"""
        base = ExecutionConfig(
            tools=ToolsConfig(enabled=["tool_a", "tool_b"]),
        )
        override = ExecutionConfig(
            tools=ToolsConfig(enabled=["tool_c"]),
        )

        result = ConfigMerger.merge(base, override)

        assert result.tools.enabled == ["tool_c"]

    def test_merge_nested_dict_values(self):
        """测试: 嵌套字典深度合并"""
        base = ExecutionConfig(
            shell=ShellConfig(
                work_dir="/base",
                env={"KEY1": "value1", "KEY2": "value2"},
            ),
        )
        override = ExecutionConfig(
            shell=ShellConfig(
                env={"KEY2": "new_value2", "KEY3": "value3"},
            ),
        )

        result = ConfigMerger.merge(base, override)

        # 嵌套字典应该深度合并
        assert result.shell.env["KEY2"] == "new_value2"
        assert result.shell.env["KEY3"] == "value3"
        # 注意：列表替换而非合并，env 是字典所以会合并
        assert "KEY1" in result.shell.env

    def test_merge_with_method(self):
        """测试: merge_with 方法"""
        base = ExecutionConfig(
            hitl=HITLConfig(enabled=True, require_confirmation=["delete_file"]),
        )
        override = ExecutionConfig(
            hitl=HITLConfig(require_confirmation=["run_shell"]),
        )

        result = base.merge_with(override)

        assert result.hitl.enabled is True
        assert result.hitl.require_confirmation == ["run_shell"]
