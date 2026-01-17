"""
组合验证器

聚合多个验证器，按顺序执行验证
"""

from typing import TYPE_CHECKING

from core.config.validators.base import ConfigValidator, ValidationResult
from core.config.validators.sandbox_validator import SandboxValidator
from core.config.validators.security_validator import SecurityValidator

if TYPE_CHECKING:
    from core.config.execution_config import ExecutionConfig


class CompositeValidator(ConfigValidator):
    """
    组合验证器

    聚合多个验证器，收集所有错误和警告
    """

    def __init__(self, validators: list[ConfigValidator] | None = None) -> None:
        """
        初始化组合验证器

        Args:
            validators: 要执行的验证器列表
        """
        self.validators = validators or []

    def add(self, validator: ConfigValidator) -> "CompositeValidator":
        """添加验证器"""
        self.validators.append(validator)
        return self

    def validate(self, config: "ExecutionConfig") -> ValidationResult:
        """执行所有验证器"""
        result = ValidationResult(is_valid=True)

        for validator in self.validators:
            validator_result = validator.validate(config)
            result = result.merge(validator_result)

        return result

    @classmethod
    def default(cls) -> "CompositeValidator":
        """创建默认验证器组合"""
        return cls(
            [
                SandboxValidator(),
                SecurityValidator(),
            ]
        )
