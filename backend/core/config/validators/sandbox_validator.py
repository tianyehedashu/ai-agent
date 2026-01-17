"""
沙箱配置验证器
"""

from typing import TYPE_CHECKING

from core.config.execution_config import SandboxMode
from core.config.validators.base import ConfigValidator, ValidationResult

if TYPE_CHECKING:
    from core.config.execution_config import ExecutionConfig


class SandboxValidator(ConfigValidator):
    """沙箱配置验证器"""

    def validate(self, config: "ExecutionConfig") -> ValidationResult:
        """验证沙箱配置"""
        errors: list[str] = []
        warnings: list[str] = []

        sandbox = config.sandbox

        # Docker 模式必须指定镜像
        if sandbox.mode == SandboxMode.DOCKER and not sandbox.docker.image:
            errors.append("Docker mode requires 'sandbox.docker.image' to be specified")

        # 网络配置警告
        if sandbox.network.enabled and not sandbox.network.allowed_hosts:
            warnings.append(
                "Network enabled but no 'sandbox.network.allowed_hosts' specified - all hosts allowed"
            )

        # 资源限制检查
        if sandbox.timeout_seconds < 1:
            errors.append("sandbox.timeout_seconds must be at least 1")

        if sandbox.timeout_seconds > 3600:
            warnings.append("sandbox.timeout_seconds > 3600 (1 hour) may cause issues")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
