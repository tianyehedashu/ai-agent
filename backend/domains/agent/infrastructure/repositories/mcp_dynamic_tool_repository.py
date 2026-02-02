"""
MCP Dynamic Tool Repository - MCP 动态工具仓储

按 server_kind + server_id 管理动态工具，无所有权过滤。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.mcp_dynamic_tool import MCPDynamicTool


class MCPDynamicToolRepository:
    """MCP 动态工具仓储"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_server(self, server_kind: str, server_id: str) -> list[MCPDynamicTool]:
        """按 server 列出动态工具"""
        q = select(MCPDynamicTool).where(
            MCPDynamicTool.server_kind == server_kind,
            MCPDynamicTool.server_id == server_id,
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_by_tool_key(
        self, server_kind: str, server_id: str, tool_key: str
    ) -> MCPDynamicTool | None:
        """按 server + tool_key 获取一条"""
        q = select(MCPDynamicTool).where(
            MCPDynamicTool.server_kind == server_kind,
            MCPDynamicTool.server_id == server_id,
            MCPDynamicTool.tool_key == tool_key,
        )
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def add(
        self,
        server_kind: str,
        server_id: str,
        tool_key: str,
        tool_type: str,
        config_json: dict,
        description: str | None = None,
        enabled: bool = True,
    ) -> MCPDynamicTool:
        """新增一条动态工具（同 server 下 tool_key 唯一，由唯一约束保证）"""
        row = MCPDynamicTool(
            server_kind=server_kind,
            server_id=server_id,
            tool_key=tool_key,
            tool_type=tool_type,
            config_json=config_json,
            description=description,
            enabled=enabled,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update_by_tool_key(
        self,
        server_kind: str,
        server_id: str,
        tool_key: str,
        **kwargs: object,
    ) -> MCPDynamicTool | None:
        """按 server + tool_key 更新，仅更新 kwargs 中提供的字段（含 description=None 清空）。返回更新后的记录或 None。"""
        row = await self.get_by_tool_key(server_kind, server_id, tool_key)
        if not row:
            return None
        if "tool_type" in kwargs:
            row.tool_type = kwargs["tool_type"]
        if "config_json" in kwargs:
            row.config_json = kwargs["config_json"]
        if "description" in kwargs:
            row.description = kwargs["description"]
        if "enabled" in kwargs:
            row.enabled = kwargs["enabled"]
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_by_tool_key(self, server_kind: str, server_id: str, tool_key: str) -> bool:
        """按 server + tool_key 删除，返回是否删除了记录"""
        row = await self.get_by_tool_key(server_kind, server_id, tool_key)
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True
