"""
Tool Registry - 工具注册表

管理工具的注册和检索
"""

from typing import Any

from core.types import ToolCategory, ToolResult
from tools.base import BaseTool, tool_registry


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
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"Tool execution error: {e!s}",
            )
