"""
MCP 工具包装器

将 LangChain MCP 工具包装为 BaseTool，以便集成到工具注册表。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from domains.agent.domain.types import ToolCategory, ToolResult
from domains.agent.infrastructure.tools.base import BaseTool
from utils.logging import get_logger

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool as LangChainBaseTool

logger = get_logger(__name__)


class MCPToolWrapper(BaseTool):
    """
    MCP 工具包装器

    将 LangChain MCP 工具包装为系统 BaseTool。
    支持两种模式：
    1. 直接包装 LangChain 工具
    2. 通过 MCP 客户端间接调用
    """

    # 类变量将在实例化时设置
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.EXTERNAL
    requires_confirmation: bool = False

    def __init__(
        self,
        mcp_client: Any = None,
        server_name: str = "",
        tool_name: str = "",
        tool_definition: dict[str, Any] | None = None,
        langchain_tool: "LangChainBaseTool | None" = None,
    ):
        """
        初始化 MCP 工具包装器。

        支持两种初始化方式：
        1. 传入 langchain_tool：直接包装 LangChain 工具
        2. 传入 mcp_client + server_name + tool_name：通过客户端间接调用

        Args:
            mcp_client: MCP 客户端实例（ConfiguredMCPManager 或 MCPClient）
            server_name: MCP 服务器名称
            tool_name: 工具名称
            tool_definition: 工具定义（从 MCP 服务器获取）
            langchain_tool: LangChain 工具实例（直接包装模式）
        """
        super().__init__()

        self._langchain_tool = langchain_tool
        self.mcp_client = mcp_client
        self.server_name = server_name
        self.tool_name = tool_name
        self._tool_schema: dict[str, Any] = tool_definition or {}

        if langchain_tool:
            # 直接包装 LangChain 工具
            self.name = langchain_tool.name
            self.description = langchain_tool.description or f"MCP tool: {langchain_tool.name}"
            self._init_schema_from_langchain_tool(langchain_tool)
        elif server_name and tool_name:
            # 通过客户端间接调用
            self.name = f"{server_name}__{tool_name}"
            self.description = self._tool_schema.get(
                "description", f"MCP tool: {tool_name}"
            )
        else:
            raise ValueError("Must provide either langchain_tool or (server_name + tool_name)")

        self.category = ToolCategory.EXTERNAL

    def _init_schema_from_langchain_tool(self, tool: "LangChainBaseTool") -> None:
        """从 LangChain 工具初始化参数 schema。"""
        if hasattr(tool, "args_schema") and tool.args_schema:
            self._tool_schema = {"inputSchema": tool.args_schema.model_json_schema()}
        else:
            self._tool_schema = {"inputSchema": {"type": "object", "properties": {}}}

    @property
    def parameters(self) -> dict[str, Any]:
        """获取 JSON Schema 参数定义。"""
        input_schema = self._tool_schema.get("inputSchema", {})
        if not input_schema:
            return {"type": "object", "properties": {}}
        return input_schema

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 MCP 工具。"""
        try:
            if self._langchain_tool:
                # 直接调用 LangChain 工具
                result = await self._langchain_tool.ainvoke(kwargs)
                return ToolResult(
                    tool_call_id="",
                    success=True,
                    output=str(result) if result is not None else "",
                    error=None,
                )
            elif self.mcp_client:
                # 通过客户端调用
                result = await self.mcp_client.call_tool(
                    server_name=self.server_name,
                    tool_name=self.tool_name,
                    arguments=kwargs,
                )

                success = result.get("success", False)
                output = str(result.get("result", ""))
                error = result.get("error") if not success else None

                return ToolResult(
                    tool_call_id="",
                    success=success,
                    output=output,
                    error=error,
                )
            else:
                return ToolResult(
                    tool_call_id="",
                    success=False,
                    output="",
                    error="MCP tool not properly configured",
                )
        except Exception as e:
            logger.exception("MCP tool execution failed: %s", self.name)
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"MCP tool error ({self.name}): {e}",
            )


def wrap_langchain_tools(tools: list["LangChainBaseTool"]) -> list[MCPToolWrapper]:
    """
    将 LangChain 工具列表包装为 MCPToolWrapper 列表。

    Args:
        tools: LangChain 工具列表

    Returns:
        MCPToolWrapper 列表
    """
    wrapped = []
    for tool in tools:
        try:
            wrapper = MCPToolWrapper(langchain_tool=tool)
            wrapped.append(wrapper)
            logger.debug("Wrapped LangChain tool: %s", tool.name)
        except Exception as e:
            logger.error("Failed to wrap LangChain tool %s: %s", tool.name, e)
    return wrapped
