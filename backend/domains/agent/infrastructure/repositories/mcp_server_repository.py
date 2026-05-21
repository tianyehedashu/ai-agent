"""MCP Server Repository - 用户级与系统级 MCP 服务器"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from domains.agent.domain.config.mcp_config import MCPServerEntityConfig
from domains.agent.infrastructure.models.mcp_server import MCPServer
from domains.agent.infrastructure.models.system_mcp_server import SystemMCPServer
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.db.tenant_resolve import resolve_tenant_id_for_write

from utils.logging import get_logger

logger = get_logger(__name__)


class MCPServerRepository(TenantScopedRepositoryBase[MCPServer]):
    """用户 tenant 级 MCP + 只读系统 MCP 列表。"""

    @property
    def model_class(self) -> type[MCPServer]:
        return MCPServer

    async def get_by_id(self, server_id: uuid.UUID) -> MCPServer | SystemMCPServer | None:
        user = await self.get_in_tenants(server_id)
        if user is not None:
            return user
        result = await self.db.execute(
            select(SystemMCPServer).where(SystemMCPServer.id == server_id)
        )
        return result.scalar_one_or_none()

    async def list_available(
        self,
    ) -> tuple[list[SystemMCPServer], list[MCPServer]]:
        system_result = await self.db.execute(select(SystemMCPServer))
        system_servers = list(system_result.scalars().all())
        user_servers = await self.find_for_tenants(skip=0, limit=500)
        return system_servers, user_servers

    async def get_by_name(self, name: str) -> MCPServer | SystemMCPServer | None:
        sys_row = await self.db.execute(
            select(SystemMCPServer).where(SystemMCPServer.name == name)
        )
        found = sys_row.scalar_one_or_none()
        if found is not None:
            return found
        q = select(MCPServer).where(MCPServer.name == name)
        q = self._apply_tenant_scope(q)
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def create(
        self,
        config: MCPServerEntityConfig,
        user_id: uuid.UUID | None = None,  # noqa: ARG002 — 归属由 tenant 解析
    ) -> MCPServer:
        if config.scope.value != "user":
            msg = "user-scoped MCPServer must use scope=user; system servers use SystemMCPServer"
            raise ValueError(msg)
        tenant_id = await resolve_tenant_id_for_write(self.db)
        server = MCPServer(
            tenant_id=tenant_id,
            name=config.name,
            display_name=config.display_name,
            url=config.url,
            scope=config.scope.value,
            env_type=config.env_type.value,
            env_config=config.env_config,
            enabled=config.enabled,
            template_id=getattr(config, "template_id", None),
            inherit_defaults=getattr(config, "inherit_defaults", False),
        )
        self.db.add(server)
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def update(
        self,
        server_id: uuid.UUID,
        config: MCPServerEntityConfig,
    ) -> MCPServer | None:
        server = await self.get_in_tenants(server_id)
        if not server:
            return None
        server.display_name = config.display_name
        server.url = config.url
        server.env_type = config.env_type.value
        server.env_config = config.env_config
        server.enabled = config.enabled
        if hasattr(config, "template_id"):
            server.template_id = config.template_id
        if hasattr(config, "inherit_defaults"):
            server.inherit_defaults = config.inherit_defaults
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def toggle(self, server_id: uuid.UUID, enabled: bool) -> MCPServer | None:
        server = await self.get_in_tenants(server_id)
        if not server:
            return None
        server.enabled = enabled
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def toggle_system(self, server_id: uuid.UUID, enabled: bool) -> SystemMCPServer | None:
        result = await self.db.execute(
            select(SystemMCPServer).where(SystemMCPServer.id == server_id)
        )
        server = result.scalar_one_or_none()
        if server is None:
            return None
        server.enabled = enabled
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def update_system(
        self,
        server_id: uuid.UUID,
        config: MCPServerEntityConfig,
    ) -> SystemMCPServer | None:
        result = await self.db.execute(
            select(SystemMCPServer).where(SystemMCPServer.id == server_id)
        )
        server = result.scalar_one_or_none()
        if server is None:
            return None
        server.display_name = config.display_name
        server.url = config.url
        server.env_type = config.env_type.value
        server.env_config = config.env_config
        server.enabled = config.enabled
        if hasattr(config, "template_id"):
            server.template_id = config.template_id
        if hasattr(config, "inherit_defaults"):
            server.inherit_defaults = config.inherit_defaults
        await self.db.flush()
        await self.db.refresh(server)
        return server

    async def count_by_scope(self) -> dict[str, int]:
        system_result = await self.db.execute(
            select(func.count()).select_from(SystemMCPServer)
        )
        user_count = await self.count_for_tenants()
        return {
            "system": int(system_result.scalar() or 0),
            "user": user_count,
        }

    async def delete(self, server_id: uuid.UUID) -> bool:
        server = await self.get_in_tenants(server_id)
        if not server:
            return False
        await self.db.delete(server)
        await self.db.flush()
        return True

    async def delete_system(self, server_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(SystemMCPServer).where(SystemMCPServer.id == server_id)
        )
        server = result.scalar_one_or_none()
        if server is None:
            return False
        await self.db.delete(server)
        await self.db.flush()
        return True
