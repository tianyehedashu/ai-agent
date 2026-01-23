"""
工具配置验证器
"""

from typing import TYPE_CHECKING, Any

from .base import ConfigValidator, ValidationResult

if TYPE_CHECKING:
    from ..execution_config import ExecutionConfig


class ToolValidator(ConfigValidator):
    """
    工具配置验证器

    验证配置中引用的工具是否存在
    """

    def __init__(self, tool_definitions: dict[str, Any] | None = None) -> None:
        """
        初始化工具验证器

        Args:
            tool_definitions: 已知的工具定义，用于验证工具是否存在
        """
        self.tool_definitions = tool_definitions or {}

    def validate(self, config: "ExecutionConfig") -> ValidationResult:
        """验证工具配置"""
        errors: list[str] = []
        warnings: list[str] = []

        tools = config.tools

        # 检查启用的工具是否存在
        if self.tool_definitions:
            for tool_name in tools.enabled:
                if tool_name not in self.tool_definitions:
                    warnings.append(f"Unknown tool in enabled list: '{tool_name}'")

            for tool_name in tools.disabled:
                if tool_name not in self.tool_definitions:
                    warnings.append(f"Unknown tool in disabled list: '{tool_name}'")

            for tool_name in tools.require_confirmation:
                if tool_name not in self.tool_definitions:
                    warnings.append(f"Unknown tool in require_confirmation: '{tool_name}'")

        # 检查冲突：同时在 enabled 和 disabled 中
        conflict = set(tools.enabled) & set(tools.disabled)
        if conflict:
            errors.append(f"Tools cannot be both enabled and disabled: {', '.join(conflict)}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
