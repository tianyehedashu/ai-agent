"""
Tool Registry - 工具注册表

管理工具的注册和检索
"""

import fnmatch
from typing import TYPE_CHECKING, Any, ClassVar

from core.types import ToolCategory, ToolResult
from tools.base import BaseTool, tool_registry

if TYPE_CHECKING:
    from core.config.execution_config import ExecutionConfig


class ToolRegistry:
    """工具注册表管理器"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._load_builtin_tools()

    def _load_builtin_tools(self) -> None:
        """加载内置工具"""
        # 从全局注册表实例化所有工具
        for name, tool_cls in tool_registry.items():
            self._tools[name] = tool_cls()

    def register(self, tool: BaseTool) -> None:
        """注册工具实例"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """获取工具"""
        return self._tools.get(name)

    def list_all(self) -> list[BaseTool]:
        """列出所有工具"""
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> list[BaseTool]:
        """按分类列出工具"""
        return [t for t in self._tools.values() if t.category == category]

    def get_tools_for_agent(self, tool_names: list[str]) -> list[BaseTool]:
        """获取指定的工具列表"""
        tools = []
        for name in tool_names:
            tool = self.get(name)
            if tool:
                tools.append(tool)
        return tools

    def to_openai_tools(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """转换为 OpenAI 工具格式"""
        tools = self.get_tools_for_agent(tool_names) if tool_names else self.list_all()
        return [t.to_openai_tool() for t in tools]

    def to_anthropic_tools(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """转换为 Anthropic 工具格式"""
        tools = self.get_tools_for_agent(tool_names) if tool_names else self.list_all()
        return [t.to_anthropic_tool() for t in tools]

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"Tool not found: {name}",
            )

        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            # 提供详细的错误信息，包括异常类型和消息
            error_msg = f"{type(e).__name__}: {str(e)!s}" if str(e) else type(e).__name__
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"Tool execution error: {error_msg}",
            )


class ConfiguredToolRegistry(ToolRegistry):
    """
    基于 ExecutionConfig 的工具注册表

    根据执行环境配置过滤和管理工具，并将配置注入到需要沙箱执行的工具中。
    """

    # 需要注入 ExecutionConfig 的工具列表
    SANDBOX_AWARE_TOOLS: ClassVar[set[str]] = {"run_shell", "run_python"}

    def __init__(self, config: "ExecutionConfig") -> None:
        """
        初始化配置化的工具注册表

        Args:
            config: 执行环境配置
        """
        super().__init__()
        self.config = config
        self._inject_execution_config()
        self._filter_enabled_tools()

    def _inject_execution_config(self) -> None:
        """将执行环境配置注入到需要沙箱执行的工具中"""
        for tool_name in self.SANDBOX_AWARE_TOOLS:
            tool = self._tools.get(tool_name)
            if tool and hasattr(tool.__class__, "execution_config"):
                tool.__class__.execution_config = self.config

    def _filter_enabled_tools(self) -> None:
        """根据配置过滤启用的工具"""
        enabled = set(self.config.tools.enabled)
        disabled = set(self.config.tools.disabled)

        # 如果没有指定启用的工具，默认全部启用
        if not enabled:
            return

        # 过滤工具：只保留启用的，排除禁用的
        tools_to_remove = []
        for name in self._tools:
            if name in disabled or (enabled and name not in enabled):
                tools_to_remove.append(name)

        for name in tools_to_remove:
            del self._tools[name]

    def requires_confirmation(self, tool_name: str) -> bool:
        """
        检查工具是否需要人工确认

        Args:
            tool_name: 工具名称

        Returns:
            是否需要确认
        """
        # 检查自动批准模式
        auto_approve_patterns = (
            self.config.tools.auto_approve_patterns + self.config.hitl.auto_approve_patterns
        )
        for pattern in auto_approve_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                return False

        # 检查需要确认列表
        require_confirm = (
            self.config.tools.require_confirmation + self.config.hitl.require_confirmation
        )
        if tool_name in require_confirm:
            return True

        # 检查工具本身的配置
        tool_config = self.config.tools.config.get(tool_name, {})
        return tool_config.get("requires_confirmation", False)

    def get_tool_config(self, tool_name: str) -> dict[str, Any]:
        """
        获取工具的配置

        Args:
            tool_name: 工具名称

        Returns:
            工具配置字典
        """
        return self.config.tools.config.get(tool_name, {})
