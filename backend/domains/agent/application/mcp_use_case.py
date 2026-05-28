"""
MCP Use Case - MCP 管理用例

提供 MCP 服务器的业务逻辑
"""

from datetime import datetime
import json
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
import tiktoken

from domains.agent.application.mcp_api_models import (
    MCPServerCreateRequest,
    MCPServersListResponse,
    MCPServerUpdateRequest,
    MCPToolInfo,
    MCPToolsListResponse,
)
from domains.agent.application.mcp_server_mapper import mcp_server_to_response
from domains.agent.domain.config.mcp_config import (
    MCPEnvironmentType,
    MCPScope,
    MCPServerEntityConfig,
    MCPTemplate,
)
from domains.agent.domain.config.templates import BUILTIN_TEMPLATES, get_effective_env_config
from domains.agent.domain.policies.mcp_access import (
    McpAccessAction,
    assert_mcp_access,
    assert_mcp_delete,
    mcp_server_kind,
)
from domains.agent.infrastructure.models.mcp_server import MCPServer
from domains.agent.infrastructure.models.system_mcp_server import SystemMCPServer
from domains.agent.infrastructure.repositories.mcp_server_repository import (
    MCPServerRepository,
)
from domains.agent.infrastructure.tools.mcp.client import test_mcp_connection
from domains.identity.presentation.schemas import CurrentUser
from libs.exceptions import ConflictError, NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


def _is_system_server(server: MCPServer | SystemMCPServer) -> bool:
    return isinstance(server, SystemMCPServer)


class MCPManagementUseCase:
    """MCP 管理用例"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = MCPServerRepository(db)

    async def _get_server_or_raise(self, server_id: uuid.UUID) -> MCPServer | SystemMCPServer:
        server = await self.repository.get_by_id(server_id)
        if not server:
            raise NotFoundError("MCP Server", str(server_id))
        return server

    def _assert_access(
        self,
        server: MCPServer | SystemMCPServer,
        current_user: CurrentUser,
        action: McpAccessAction,
    ) -> None:
        assert_mcp_access(
            kind=mcp_server_kind(is_system=_is_system_server(server)),
            is_platform_admin=current_user.is_admin,
            action=action,
        )

    def _entity_config_from_server(
        self, server: MCPServer | SystemMCPServer
    ) -> MCPServerEntityConfig:
        scope = MCPScope.SYSTEM if _is_system_server(server) else MCPScope.USER
        return MCPServerEntityConfig(
            id=server.id,
            name=server.name,
            display_name=server.display_name,
            url=server.url,
            scope=scope,
            env_type=MCPEnvironmentType(server.env_type),
            env_config=server.env_config or {},
            enabled=server.enabled,
            template_id=getattr(server, "template_id", None),
            inherit_defaults=getattr(server, "inherit_defaults", False),
        )

    def _calculate_token_count(self, tool_config: Any) -> int:
        """计算工具定义的 Token 占用"""
        try:
            encoding = tiktoken.encoding_for_model("gpt-4")
            tool_def = {
                "name": tool_config.get("name", ""),
                "description": tool_config.get("description", ""),
                "inputSchema": tool_config.get("inputSchema", {}),
            }
            tool_str = json.dumps(tool_def, ensure_ascii=False)
            return len(encoding.encode(tool_str))
        except Exception:
            tool_str = json.dumps(tool_config, ensure_ascii=False)
            return len(tool_str) // 4

    async def list_templates(self) -> list[MCPTemplate]:
        """列出所有可用的 MCP 服务器模板"""
        return BUILTIN_TEMPLATES

    async def list_servers(self, current_user: CurrentUser) -> MCPServersListResponse:
        system_servers, user_servers = await self.repository.list_available()
        owner_id = uuid.UUID(current_user.id)
        return MCPServersListResponse(
            system_servers=[mcp_server_to_response(server) for server in system_servers],
            user_servers=[
                mcp_server_to_response(server, owner_user_id=owner_id) for server in user_servers
            ],
        )

    async def add_server(self, request: MCPServerCreateRequest, current_user: CurrentUser):
        existing = await self.repository.get_by_name(request.name)
        if existing:
            raise ConflictError(
                f"MCP server name '{request.name}' already exists",
                code="SERVER_NAME_EXISTS",
            )

        if request.template_id:
            template = next((t for t in BUILTIN_TEMPLATES if t.id == request.template_id), None)
            if not template:
                raise ValidationError(
                    f"Template not found: {request.template_id}",
                    code="TEMPLATE_NOT_FOUND",
                )
            config = template.default_config.model_copy(
                update={
                    "name": request.name,
                    "url": request.url,
                    "display_name": request.display_name or template.default_config.display_name,
                    "env_type": request.env_type,
                    "env_config": request.env_config,
                    "enabled": request.enabled,
                    "template_id": request.template_id,
                    "inherit_defaults": getattr(request, "inherit_defaults", False),
                }
            )
        else:
            config = MCPServerEntityConfig(
                name=request.name,
                display_name=request.display_name,
                url=request.url,
                scope=MCPScope.USER,
                env_type=request.env_type,
                env_config=request.env_config,
                enabled=request.enabled,
                template_id=request.template_id,
                inherit_defaults=getattr(request, "inherit_defaults", False),
            )

        server = await self.repository.create(config=config)
        await self.db.commit()

        logger.info(
            "Created MCP server: %s for user %s",
            server.name,
            uuid.UUID(current_user.id),
        )
        return server

    async def update_server(
        self,
        server_id: uuid.UUID,
        request: MCPServerUpdateRequest,
        current_user: CurrentUser,
    ):
        server = await self._get_server_or_raise(server_id)
        self._assert_access(server, current_user, McpAccessAction.MUTATE)

        config = self._entity_config_from_server(server)
        update_data = request.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(config, field):
                setattr(config, field, value)

        if _is_system_server(server):
            updated_server = await self.repository.update_system(server_id, config)
        else:
            updated_server = await self.repository.update(server_id, config)
        if not updated_server:
            raise NotFoundError("MCP Server", str(server_id))

        await self.db.commit()
        logger.info("Updated MCP server: %s", server.name)
        return updated_server

    async def delete_server(self, server_id: uuid.UUID, current_user: CurrentUser) -> None:
        server = await self._get_server_or_raise(server_id)
        assert_mcp_delete(
            kind=mcp_server_kind(is_system=_is_system_server(server)),
            is_platform_admin=current_user.is_admin,
        )

        if _is_system_server(server):
            deleted = await self.repository.delete_system(server_id)
        else:
            deleted = await self.repository.delete(server_id)
        if not deleted:
            raise NotFoundError("MCP Server", str(server_id))

        await self.db.commit()
        logger.info("Deleted MCP server: %s", server.name)

    async def toggle_server(self, server_id: uuid.UUID, enabled: bool, current_user: CurrentUser):
        server = await self._get_server_or_raise(server_id)
        self._assert_access(server, current_user, McpAccessAction.MUTATE)

        if _is_system_server(server):
            updated = await self.repository.toggle_system(server_id, enabled)
        else:
            updated = await self.repository.toggle(server_id, enabled)
        if not updated:
            raise NotFoundError("MCP Server", str(server_id))

        await self.db.commit()
        logger.info(
            "Toggled MCP server %s: %s",
            updated.name,
            "enabled" if enabled else "disabled",
        )
        return updated

    async def test_connection(
        self, server_id: uuid.UUID, current_user: CurrentUser
    ) -> dict[str, Any]:
        server = await self._get_server_or_raise(server_id)
        self._assert_access(server, current_user, McpAccessAction.READ_TOOLS)

        if not server.enabled:
            return {
                "success": False,
                "message": "服务器已禁用",
                "server_name": server.name,
                "server_url": server.url,
                "connection_status": "failed",
                "error_details": "服务器处于禁用状态，请先启用后再测试连接",
                "tools_count": 0,
                "tools_sample": [],
            }

        logger.info("Testing MCP connection for server: %s (%s)", server.name, server.url)

        effective_env_config = get_effective_env_config(
            server.env_config or {},
            server.template_id,
            getattr(server, "inherit_defaults", False),
        )
        try:
            success, tools, error = await test_mcp_connection(
                url=server.url,
                env_config=effective_env_config,
                timeout=30.0,
            )

            if success:
                server.connection_status = "connected"
                server.last_connected_at = datetime.now().isoformat()
                server.last_error = None
                server.available_tools = {
                    "tools": tools,
                    "count": len(tools),
                    "updated_at": datetime.now().isoformat(),
                }
                message = f"连接成功！发现 {len(tools)} 个可用工具"
                tools_sample = [tool["name"] for tool in tools[:5]]
            else:
                server.connection_status = "failed"
                server.last_connected_at = datetime.now().isoformat()
                server.last_error = error or "连接失败"
                message = f"连接失败：{error}"
                tools_sample = []

            await self.db.commit()

            return {
                "success": success,
                "message": message,
                "server_name": server.name,
                "server_url": server.url,
                "connection_status": server.connection_status,
                "error_details": server.last_error if not success else None,
                "tools_count": len(tools) if success else 0,
                "tools_sample": tools_sample,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error("MCP connection test failed for %s: %s", server.name, error_msg)

            server.connection_status = "failed"
            server.last_connected_at = datetime.now().isoformat()
            server.last_error = error_msg

            await self.db.commit()

            return {
                "success": False,
                "message": f"连接测试异常：{error_msg}",
                "server_name": server.name,
                "server_url": server.url,
                "connection_status": "failed",
                "error_details": error_msg,
                "tools_count": 0,
                "tools_sample": [],
            }

    async def list_server_tools(
        self, server_id: uuid.UUID, current_user: CurrentUser
    ) -> MCPToolsListResponse:
        server = await self._get_server_or_raise(server_id)
        self._assert_access(server, current_user, McpAccessAction.READ_TOOLS)

        tools_data = server.available_tools or {}
        tools: list[MCPToolInfo] = []

        if isinstance(tools_data, dict) and "tools" in tools_data:
            tool_list = tools_data["tools"]
        else:
            tool_list = []

        for tool in tool_list:
            if isinstance(tool, dict):
                tools.append(
                    MCPToolInfo(
                        name=tool.get("name", ""),
                        description=tool.get("description"),
                        input_schema=tool.get("inputSchema", {}),
                        enabled=tool.get("enabled", True),
                        token_count=self._calculate_token_count(tool),
                    )
                )

        total_tokens = sum(t.token_count for t in tools)
        enabled_count = sum(1 for t in tools if t.enabled)

        return MCPToolsListResponse(
            server_id=server.id,
            server_name=server.name,
            tools=tools,
            total_tokens=total_tokens,
            enabled_count=enabled_count,
        )

    async def toggle_tool_enabled(
        self, server_id: uuid.UUID, tool_name: str, enabled: bool, current_user: CurrentUser
    ) -> MCPToolInfo:
        server = await self._get_server_or_raise(server_id)
        self._assert_access(server, current_user, McpAccessAction.MUTATE_SYSTEM_TOOLS)

        tools_data = dict(server.available_tools or {})
        if "tools" in tools_data:
            tool_list = tools_data["tools"]
            for tool in tool_list:
                if isinstance(tool, dict) and tool.get("name") == tool_name:
                    tool["enabled"] = enabled
                    break

        server.available_tools = tools_data
        await self.db.commit()

        tool_config = next(
            (
                t
                for t in tools_data.get("tools", [])
                if isinstance(t, dict) and t.get("name") == tool_name
            ),
            {},
        )

        return MCPToolInfo(
            name=tool_name,
            description=tool_config.get("description"),
            input_schema=tool_config.get("inputSchema", {}),
            enabled=enabled,
            token_count=self._calculate_token_count(tool_config),
        )
