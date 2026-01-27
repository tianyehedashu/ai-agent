"""
MCP 工具包装器

将 MCP 服务器的工具包装为 BaseTool，以便集成到工具注册表
"""

from typing import Any

from domains.agent.domain.types import ToolCategory, ToolResult
from domains.agent.infrastructure.tools.base import BaseTool


class MCPToolWrapper(BaseTool):
    """
    MCP 工具包装器

    将 MCP 服务器的工具动态包装为 BaseTool
    """

    # 类变量将在实例化时设置
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.EXTERNAL
    requires_confirmation: bool = False

    def __init__(
        self,
        mcp_client,
        server_name: str,
        tool_name: str,
        tool_definition: dict[str, Any],
    ):
        """
        初始化 MCP 工具包装器

        Args:
            mcp_client: MCP 客户端实例
            server_name: MCP 服务器名称
            tool_name: 工具名称
            tool_definition: 工具定义（从 MCP 服务器获取）
        """
        super().__init__()
        self.mcp_client = mcp_client
        self.server_name = server_name
        self.tool_name = tool_name

        # 从工具定义中提取元数据
        self.name = f"{server_name}__{tool_name}"
        self.description = tool_definition.get("description", f"MCP tool: {tool_name}")
        self.category = ToolCategory.EXTERNAL

        # 提取参数 schema
        self._tool_schema = tool_definition

    @property
    def parameters(self) -> dict[str, Any]:
        """获取 JSON Schema 参数定义"""
        input_schema = self._tool_schema.get("inputSchema", {})
        if not input_schema:
            return {"type": "object", "properties": {}}
        return input_schema

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行 MCP 工具"""
        try:
            # 调用 MCP 客户端
            result = await self.mcp_client.call_tool(
                server_name=self.server_name,
                tool_name=self.tool_name,
                arguments=kwargs,
            )

            # 构造 ToolResult
            return ToolResult(
                tool_call_id="",  # MCP 不提供 tool_call_id
                success=True,
                output=str(result),
                error=None,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                success=False,
                output="",
                error=f"MCP tool error ({self.server_name}__{self.tool_name}): {e}",
            )
