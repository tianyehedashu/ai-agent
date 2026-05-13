"""
MCP Dynamic Tool Use Case - MCP 动态工具用例

为客户端直连 MCP（Streamable HTTP）提供动态工具的增删改查。
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.mcp.dynamic_tool import DynamicToolType
from domains.agent.infrastructure.repositories.mcp_dynamic_tool_repository import (
    MCPDynamicToolRepository,
)
from libs.exceptions import ConflictError, NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

SERVER_KIND_STREAMABLE_HTTP = "streamable_http"


class MCPDynamicToolUseCase:
    """MCP 动态工具用例"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MCPDynamicToolRepository(db)

    async def list_dynamic_tools(self, server_name: str) -> list[dict]:
        """列出某客户端直连 MCP 的动态工具（server_name 即 server_id）。"""
        rows = await self.repo.list_by_server(SERVER_KIND_STREAMABLE_HTTP, server_name)
        return [
            {
                "id": str(r.id),
                "tool_key": r.tool_key,
                "tool_type": r.tool_type,
                "config": r.config_json,
                "description": r.description,
                "enabled": r.enabled,
            }
            for r in rows
        ]

    async def add_dynamic_tool(
        self,
        server_name: str,
        tool_key: str,
        tool_type: str,
        config: dict,
        description: str | None = None,
    ) -> dict:
        """添加一条动态工具。校验 server_name 与 tool_type，同 server 下 tool_key 唯一。"""
        if not tool_key or not tool_key.strip():
            raise ValidationError("tool_key is required", code="INVALID_TOOL_KEY")
        if tool_type not in (t.value for t in DynamicToolType):
            raise ValidationError(
                f"Unknown tool_type: {tool_type}",
                code="INVALID_TOOL_TYPE",
            )
        existing = await self.repo.get_by_tool_key(
            SERVER_KIND_STREAMABLE_HTTP, server_name, tool_key.strip()
        )
        if existing:
            raise ConflictError(
                f"Tool key already exists: {tool_key}",
                code="TOOL_KEY_EXISTS",
            )
        row = await self.repo.add(
            server_kind=SERVER_KIND_STREAMABLE_HTTP,
            server_id=server_name,
            tool_key=tool_key.strip(),
            tool_type=tool_type,
            config_json=config or {},
            description=description,
            enabled=True,
        )
        await self.db.commit()
        return {
            "id": str(row.id),
            "tool_key": row.tool_key,
            "tool_type": row.tool_type,
            "config": row.config_json,
            "description": row.description,
            "enabled": row.enabled,
        }

    async def update_dynamic_tool(self, server_name: str, tool_key: str, **updates: Any) -> dict:
        """更新一条动态工具。仅更新请求中传入的字段（exclude_unset）。tool_key 不可改。"""
        existing = await self.repo.get_by_tool_key(
            SERVER_KIND_STREAMABLE_HTTP, server_name, tool_key
        )
        if not existing:
            raise NotFoundError("Dynamic tool", f"{server_name}/{tool_key}")
        if "tool_type" in updates and updates["tool_type"] not in (
            t.value for t in DynamicToolType
        ):
            raise ValidationError(
                f"Unknown tool_type: {updates['tool_type']}",
                code="INVALID_TOOL_TYPE",
            )
        repo_kwargs: dict[str, Any] = {}
        if "tool_type" in updates:
            repo_kwargs["tool_type"] = updates["tool_type"]
        if "config" in updates:
            repo_kwargs["config_json"] = updates["config"]
        if "description" in updates:
            repo_kwargs["description"] = updates["description"]
        if "enabled" in updates:
            repo_kwargs["enabled"] = updates["enabled"]
        row = await self.repo.update_by_tool_key(
            SERVER_KIND_STREAMABLE_HTTP,
            server_name,
            tool_key,
            **repo_kwargs,
        )
        await self.db.commit()
        assert row is not None
        return {
            "id": str(row.id),
            "tool_key": row.tool_key,
            "tool_type": row.tool_type,
            "config": row.config_json,
            "description": row.description,
            "enabled": row.enabled,
        }

    async def remove_dynamic_tool(self, server_name: str, tool_key: str) -> None:
        """删除一条动态工具。"""
        deleted = await self.repo.delete_by_tool_key(
            SERVER_KIND_STREAMABLE_HTTP, server_name, tool_key
        )
        if not deleted:
            raise NotFoundError("Dynamic tool", f"{server_name}/{tool_key}")
        await self.db.commit()
