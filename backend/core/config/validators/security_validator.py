"""
安全配置验证器
"""

from typing import TYPE_CHECKING

from .base import ConfigValidator, ValidationResult

if TYPE_CHECKING:
    from ..execution_config import ExecutionConfig


class SecurityValidator(ConfigValidator):
    """安全配置验证器"""

    def validate(self, config: "ExecutionConfig") -> ValidationResult:
        """验证安全配置"""
        errors: list[str] = []
        warnings: list[str] = []

        security = config.sandbox.security

        # 安全风险警告
        if not security.read_only_root:
            warnings.append(
                "sandbox.security.read_only_root is disabled - "
                "this is a security risk in production"
            )

        if not security.no_new_privileges:
            warnings.append(
                "sandbox.security.no_new_privileges is disabled - "
                "this is a security risk in production"
            )

        # 检查 capabilities
        if "ALL" not in security.drop_capabilities:
            warnings.append(
                "sandbox.security.drop_capabilities does not include 'ALL' - "
                "consider dropping all capabilities for better security"
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
