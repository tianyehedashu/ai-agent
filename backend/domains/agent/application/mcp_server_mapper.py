"""MCP ORM → Application DTO 映射。"""

from __future__ import annotations

import uuid

from domains.agent.application.mcp_api_models import MCPServerResponse
from domains.agent.infrastructure.models.mcp_server import MCPServer
from domains.agent.infrastructure.models.system_mcp_server import SystemMCPServer

__all__ = ["mcp_server_to_response"]


def mcp_server_to_response(
    server: MCPServer | SystemMCPServer,
    *,
    owner_user_id: uuid.UUID | None = None,
) -> MCPServerResponse:
    if isinstance(server, SystemMCPServer):
        return MCPServerResponse(
            id=server.id,
            name=server.name,
            display_name=server.display_name,
            url=server.url,
            scope="system",
            env_type=server.env_type,
            env_config=server.env_config or {},
            enabled=server.enabled,
            connection_status=server.connection_status,
            last_connected_at=server.last_connected_at,
            last_error=server.last_error,
            available_tools=server.available_tools or {},
            created_at=server.created_at,
            updated_at=server.updated_at,
            user_id=None,
            template_id=server.template_id,
            inherit_defaults=server.inherit_defaults,
        )
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        display_name=server.display_name,
        url=server.url,
        scope=server.scope,
        env_type=server.env_type,
        env_config=server.env_config or {},
        enabled=server.enabled,
        connection_status=server.connection_status,
        last_connected_at=server.last_connected_at,
        last_error=server.last_error,
        available_tools=server.available_tools or {},
        created_at=server.created_at,
        updated_at=server.updated_at,
        user_id=owner_user_id,
        template_id=server.template_id,
        inherit_defaults=server.inherit_defaults,
    )
