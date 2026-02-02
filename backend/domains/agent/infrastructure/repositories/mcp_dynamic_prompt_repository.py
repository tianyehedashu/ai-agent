"""
MCP Dynamic Prompt Repository - MCP 动态 Prompt 仓储

按 server_kind + server_id 管理动态 Prompt，无所有权过滤。
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.mcp_dynamic_prompt import MCPDynamicPrompt


class MCPDynamicPromptRepository:
    """MCP 动态 Prompt 仓储"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_server(self, server_kind: str, server_id: str) -> list[MCPDynamicPrompt]:
        """按 server 列出动态 Prompt"""
        q = select(MCPDynamicPrompt).where(
            MCPDynamicPrompt.server_kind == server_kind,
            MCPDynamicPrompt.server_id == server_id,
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_by_prompt_key(
        self, server_kind: str, server_id: str, prompt_key: str
    ) -> MCPDynamicPrompt | None:
        """按 server + prompt_key 获取一条"""
        q = select(MCPDynamicPrompt).where(
            MCPDynamicPrompt.server_kind == server_kind,
            MCPDynamicPrompt.server_id == server_id,
            MCPDynamicPrompt.prompt_key == prompt_key,
        )
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def add(
        self,
        server_kind: str,
        server_id: str,
        prompt_key: str,
        template: str,
        title: str | None = None,
        description: str | None = None,
        arguments_schema: list | None = None,
        enabled: bool = True,
    ) -> MCPDynamicPrompt:
        """新增一条动态 Prompt（同 server 下 prompt_key 唯一，由唯一约束保证）"""
        row = MCPDynamicPrompt(
            server_kind=server_kind,
            server_id=server_id,
            prompt_key=prompt_key,
            template=template,
            title=title,
            description=description,
            arguments_schema=arguments_schema or [],
            enabled=enabled,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def update_by_prompt_key(
        self,
        server_kind: str,
        server_id: str,
        prompt_key: str,
        **kwargs: object,
    ) -> MCPDynamicPrompt | None:
        """按 server + prompt_key 更新，仅更新 kwargs 中提供的字段。返回更新后的记录或 None。"""
        row = await self.get_by_prompt_key(server_kind, server_id, prompt_key)
        if not row:
            return None
        if "title" in kwargs:
            row.title = kwargs["title"]
        if "description" in kwargs:
            row.description = kwargs["description"]
        if "arguments_schema" in kwargs:
            row.arguments_schema = kwargs["arguments_schema"]
        if "template" in kwargs:
            row.template = kwargs["template"]
        if "enabled" in kwargs:
            row.enabled = kwargs["enabled"]
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_by_prompt_key(self, server_kind: str, server_id: str, prompt_key: str) -> bool:
        """按 server + prompt_key 删除，返回是否删除了记录"""
        row = await self.get_by_prompt_key(server_kind, server_id, prompt_key)
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True
