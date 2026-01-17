"""
配置验证器抽象基类

定义配置验证的统一接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config.execution_config import ExecutionConfig


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """合并两个验证结果"""
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


class ConfigValidator(ABC):
    """
    配置验证器抽象基类

    每个验证器负责验证配置的特定方面
    """

    @abstractmethod
    def validate(self, config: "ExecutionConfig") -> ValidationResult:
        """
        验证配置

        Args:
            config: 要验证的配置

        Returns:
            验证结果
        """
        pass
