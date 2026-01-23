"""
配置验证器单元测试
"""


from shared.infrastructure.config.execution_config import (
    DockerConfig,
    ExecutionConfig,
    SandboxConfig,
    SandboxMode,
    SecurityConfig,
    ToolsConfig,
)
from shared.infrastructure.config.validators import (
    CompositeValidator,
    SandboxValidator,
    SecurityValidator,
    ToolValidator,
    ValidationResult,
)


class TestValidationResult:
    """ValidationResult 测试"""

    def test_merge_results(self):
        """测试: 合并两个验证结果"""
        result1 = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["warning1"],
        )
        result2 = ValidationResult(
            is_valid=False,
            errors=["error1"],
            warnings=["warning2"],
        )

        merged = result1.merge(result2)

        assert merged.is_valid is False
        assert "error1" in merged.errors
        assert "warning1" in merged.warnings
        assert "warning2" in merged.warnings


class TestSandboxValidator:
    """SandboxValidator 测试"""

    def test_valid_docker_config(self):
        """测试: 有效的 Docker 配置"""
        config = ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.DOCKER,
                docker=DockerConfig(image="python:3.11"),
            )
        )

        validator = SandboxValidator()
        result = validator.validate(config)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_docker_mode_without_image(self):
        """测试: Docker 模式但没有镜像"""
        config = ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.DOCKER,
                docker=DockerConfig(image=""),
            )
        )

        validator = SandboxValidator()
        result = validator.validate(config)

        assert result.is_valid is False
        assert any("image" in e for e in result.errors)

    def test_network_enabled_without_allowed_hosts(self):
        """测试: 网络启用但没有允许的主机"""
        config = ExecutionConfig()
        config.sandbox.network.enabled = True
        config.sandbox.network.allowed_hosts = []

        validator = SandboxValidator()
        result = validator.validate(config)

        assert any("allowed_hosts" in w for w in result.warnings)


class TestSecurityValidator:
    """SecurityValidator 测试"""

    def test_secure_config(self):
        """测试: 安全的配置"""
        config = ExecutionConfig(
            sandbox=SandboxConfig(
                security=SecurityConfig(
                    read_only_root=True,
                    no_new_privileges=True,
                    drop_capabilities=["ALL"],
                )
            )
        )

        validator = SecurityValidator()
        result = validator.validate(config)

        assert result.is_valid is True
        assert len(result.warnings) == 0

    def test_insecure_config(self):
        """测试: 不安全的配置会产生警告"""
        config = ExecutionConfig(
            sandbox=SandboxConfig(
                security=SecurityConfig(
                    read_only_root=False,
                    no_new_privileges=False,
                    drop_capabilities=[],
                )
            )
        )

        validator = SecurityValidator()
        result = validator.validate(config)

        assert result.is_valid is True  # 只是警告，不是错误
        assert len(result.warnings) >= 2


class TestToolValidator:
    """ToolValidator 测试"""

    def test_conflicting_tools(self):
        """测试: 工具同时在 enabled 和 disabled 中"""
        config = ExecutionConfig(
            tools=ToolsConfig(
                enabled=["run_python", "run_shell"],
                disabled=["run_python"],  # 冲突!
            )
        )

        validator = ToolValidator()
        result = validator.validate(config)

        assert result.is_valid is False
        assert any("both enabled and disabled" in e for e in result.errors)

    def test_unknown_tools_warning(self):
        """测试: 未知工具产生警告"""
        tool_defs = {"run_python": {}, "run_shell": {}}

        config = ExecutionConfig(
            tools=ToolsConfig(
                enabled=["unknown_tool"],
            )
        )

        validator = ToolValidator(tool_definitions=tool_defs)
        result = validator.validate(config)

        assert any("Unknown tool" in w for w in result.warnings)


class TestCompositeValidator:
    """CompositeValidator 测试"""

    def test_combines_all_validators(self):
        """测试: 组合所有验证器的结果"""
        # 创建一个同时有沙箱错误和安全警告的配置
        config = ExecutionConfig(
            sandbox=SandboxConfig(
                mode=SandboxMode.DOCKER,
                docker=DockerConfig(image=""),  # 错误
                security=SecurityConfig(
                    read_only_root=False,  # 警告
                ),
            )
        )

        validator = CompositeValidator(
            [
                SandboxValidator(),
                SecurityValidator(),
            ]
        )
        result = validator.validate(config)

        assert result.is_valid is False  # 有错误
        assert len(result.errors) >= 1
        assert len(result.warnings) >= 1

    def test_default_validator(self):
        """测试: 默认验证器组合"""
        validator = CompositeValidator.default()
        config = ExecutionConfig()
        result = validator.validate(config)

        # 默认配置应该是有效的
        assert result.is_valid is True

    def test_add_validator(self):
        """测试: 动态添加验证器"""
        validator = CompositeValidator()
        validator.add(SandboxValidator())
        validator.add(SecurityValidator())

        assert len(validator.validators) == 2
