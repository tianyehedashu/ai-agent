"""
MCP 适配器

将 MCP 工具适配为系统工具接口
"""

from typing import Any

from domains.runtime.infrastructure.tools.base import BaseTool, ToolCategory, ToolResult
from domains.runtime.infrastructure.tools.mcp.client import MCPClient
from utils.logging import get_logger

logger = get_logger(__name__)


class MCPAdapter(BaseTool):
    """
    MCP 工具适配器

    将 MCP 协议的工具适配为系统工具
    """

    def __init__(
        self,
        mcp_client: MCPClient,
        tool_name: str,
        tool_description: str,
        tool_schema: dict[str, Any],
    ) -> None:
        self.mcp_client = mcp_client
        self._tool_name = tool_name
        self._tool_description = tool_description
        self._tool_schema = tool_schema

    @property
    def name(self) -> str:
        return self._tool_name

    @property
    def description(self) -> str:
        return self._tool_description

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.EXTERNAL

    @property
    def parameters(self) -> dict[str, Any]:
        return self._tool_schema.get("parameters", {})

    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        try:
            result = await self.mcp_client.call_tool(self._tool_name, kwargs)
            return ToolResult(
                success=True,
                output=str(result.get("result", "")),
            )
        except Exception as e:
            logger.exception("MCP tool execution failed: %s", e)
            return ToolResult(
                success=False,
                output="",
                error=str(e),
            )
