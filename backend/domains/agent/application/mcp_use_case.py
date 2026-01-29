"""
MCP Use Case - MCP 管理用例

提供 MCP 服务器的业务逻辑
"""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.config.mcp_config import (
    MCPScope,
    MCPServerEntityConfig,
    MCPTemplate,
)
from domains.agent.domain.config.templates import BUILTIN_TEMPLATES, get_effective_env_config
from domains.agent.infrastructure.repositories.mcp_server_repository import (
    MCPServerRepository,
)
from domains.agent.infrastructure.tools.mcp.client import test_mcp_connection
from domains.agent.presentation.schemas.mcp_schemas import (
    MCPServerCreateRequest,
    MCPServerResponse,
    MCPServersListResponse,
    MCPServerUpdateRequest,
    MCPToolInfo,
    MCPToolsListResponse,
)
from domains.identity.presentation.schemas import CurrentUser
from exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


class MCPManagementUseCase:
    """MCP 管理用例"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repository = MCPServerRepository(db)

    def _calculate_token_count(self, tool_config: Any) -> int:
        """计算工具定义的 Token 占用"""
        import json

        try:
            import tiktoken

            # 使用 GPT-4 的 tokenizer
            encoding = tiktoken.encoding_for_model("gpt-4")

            # 构建工具定义字符串
            tool_def = {
                "name": tool_config.get("name", ""),
                "description": tool_config.get("description", ""),
                "inputSchema": tool_config.get("inputSchema", {}),
            }
            tool_str = json.dumps(tool_def, ensure_ascii=False)

            # 计算 token 数量
            return len(encoding.encode(tool_str))
        except Exception:
            # 如果计算失败，使用估算: 1 token ≈ 4 字符
            tool_str = json.dumps(tool_config, ensure_ascii=False)
            return len(tool_str) // 4

    async def list_templates(self) -> list[MCPTemplate]:
        """列出所有可用的 MCP 服务器模板"""
        return BUILTIN_TEMPLATES

    async def list_servers(self, current_user: CurrentUser) -> MCPServersListResponse:
        """
        列出可用的 MCP 服务器

        Args:
            current_user: 当前用户

        Returns:
            服务器列表（system + user）
        """
        system_servers, user_servers = await self.repository.list_available()

        return MCPServersListResponse(
            system_servers=[MCPServerResponse.model_validate(server) for server in system_servers],
            user_servers=[MCPServerResponse.model_validate(server) for server in user_servers],
        )

    async def add_server(self, request: MCPServerCreateRequest, current_user: CurrentUser):
        """
        添加 MCP 服务器

        Args:
            request: 创建请求
            current_user: 当前用户

        Returns:
            创建的服务器配置
        """
        # 检查名称是否已存在
        existing = await self.repository.get_by_name(request.name)
        if existing:
            raise ConflictError(
                f"MCP server name '{request.name}' already exists",
                code="SERVER_NAME_EXISTS",
            )

        # 从模板加载默认配置（如果指定）
        if request.template_id:
            template = next((t for t in BUILTIN_TEMPLATES if t.id == request.template_id), None)
            if not template:
                raise ValidationError(
                    f"Template not found: {request.template_id}",
                    code="TEMPLATE_NOT_FOUND",
                )
            # 使用模板的默认配置，但允许请求中的字段覆盖
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

        # 创建服务器
        server = await self.repository.create(config=config, user_id=uuid.UUID(current_user.id))

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
        """
        更新 MCP 服务器

        Args:
            server_id: 服务器 ID
            request: 更新请求
            current_user: 当前用户

        Returns:
            更新后的服务器配置
        """
        server = await self.repository.get_by_id(server_id)
        if not server:
            raise NotFoundError("MCP Server", str(server_id))

        # 权限检查：只有管理员或创建者可以更新
        if server.scope == "system" and not current_user.is_admin:
            raise PermissionDeniedError(
                "Cannot update system server",
                code="CANNOT_UPDATE_SYSTEM_SERVER",
            )

        if server.scope == "user":
            if server.user_id is None:
                raise ValidationError(
                    "User server must have an owner",
                    code="INVALID_SERVER",
                )
            if str(server.user_id) != current_user.id and not current_user.is_admin:
                raise PermissionDeniedError(
                    "You don't have permission to update this server",
                    code="PERMISSION_DENIED",
                )

        # 构建更新配置
        config = MCPServerEntityConfig.model_validate(server)
        update_data = request.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(config, field):
                setattr(config, field, value)

        # 更新
        updated_server = await self.repository.update(server_id, config)
        if not updated_server:
            raise NotFoundError("MCP Server", str(server_id))

        await self.db.commit()

        logger.info("Updated MCP server: %s", server.name)

        return updated_server

    async def delete_server(self, server_id: uuid.UUID, current_user: CurrentUser) -> None:
        """
        删除 MCP 服务器

        Args:
            server_id: 服务器 ID
            current_user: 当前用户
        """
        server = await self.repository.get_by_id(server_id)
        if not server:
            raise NotFoundError("MCP Server", str(server_id))

        # 权限检查
        if server.scope == "system" and not current_user.is_admin:
            raise PermissionDeniedError(
                "Cannot delete system server",
                code="CANNOT_DELETE_SYSTEM_SERVER",
            )

        if server.scope == "user":
            if server.user_id is None:
                raise ValidationError(
                    "User server must have an owner",
                    code="INVALID_SERVER",
                )
            if str(server.user_id) != current_user.id:
                raise PermissionDeniedError(
                    "You don't have permission to delete this server",
                    code="PERMISSION_DENIED",
                )

        await self.repository.delete(server_id)
        await self.db.commit()

        logger.info("Deleted MCP server: %s", server.name)

    async def toggle_server(self, server_id: uuid.UUID, enabled: bool, current_user: CurrentUser):
        """
        切换服务器启用状态

        Args:
            server_id: 服务器 ID
            enabled: 启用状态
            current_user: 当前用户

        Returns:
            更新后的服务器配置
        """
        server = await self.repository.toggle(server_id, enabled)
        if not server:
            raise NotFoundError("MCP Server", str(server_id))

        await self.db.commit()

        logger.info("Toggled MCP server %s: %s", server.name, "enabled" if enabled else "disabled")

        return server

    async def test_connection(
        self, server_id: uuid.UUID, current_user: CurrentUser
    ) -> dict[str, Any]:
        """
        测试 MCP 服务器连接

        使用 langchain-mcp-adapters 进行真实的 MCP 协议连接测试。

        Args:
            server_id: 服务器 ID
            current_user: 当前用户

        Returns:
            测试结果，包含连接状态、工具列表等信息
        """
        server = await self.repository.get_by_id(server_id)
        if not server:
            raise NotFoundError("MCP Server", str(server_id))

        # 检查服务器是否启用
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

        # 使用真实 MCP 连接测试
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
                # 连接成功
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
                # 连接失败
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
            # 发生异常
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
        """获取服务器的工具列表"""
        server = await self.repository.get_by_id(server_id)
        if not server:
            raise NotFoundError("MCP Server", str(server_id))

        # 用户级服务器：仅所有者或管理员可查看工具列表
        if server.scope == "user":
            if server.user_id is None:
                raise NotFoundError("MCP Server", str(server_id))
            if str(server.user_id) != current_user.id and not current_user.is_admin:
                raise PermissionDeniedError(
                    "You don't have permission to access this server's tools",
                    code="PERMISSION_DENIED",
                )

        # 从 available_tools 中提取工具信息
        tools_data = server.available_tools or {}
        tools = []

        # 处理工具数据结构
        if isinstance(tools_data, dict) and "tools" in tools_data:
            tool_list = tools_data["tools"]
        else:
            tool_list = []

        for tool in tool_list:
            if isinstance(tool, dict):
                tool_info = MCPToolInfo(
                    name=tool.get("name", ""),
                    description=tool.get("description"),
                    input_schema=tool.get("inputSchema", {}),
                    enabled=tool.get("enabled", True),
                    token_count=self._calculate_token_count(tool),
                )
                tools.append(tool_info)

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
        """切换工具启用状态"""
        server = await self.repository.get_by_id(server_id)
        if not server:
            raise NotFoundError("MCP Server", str(server_id))

        # 权限检查
        if server.scope == "system" and not current_user.is_admin:
            raise PermissionDeniedError(
                "Cannot modify system server tools",
                code="CANNOT_MODIFY_SYSTEM_SERVER",
            )

        if server.scope == "user":
            if server.user_id is None:
                raise ValidationError(
                    "User server must have an owner",
                    code="INVALID_SERVER",
                )
            if str(server.user_id) != current_user.id and not current_user.is_admin:
                raise PermissionDeniedError(
                    "You don't have permission to modify this server",
                    code="PERMISSION_DENIED",
                )

        # 更新工具启用状态
        tools_data = dict(server.available_tools or {})
        if "tools" in tools_data:
            tool_list = tools_data["tools"]
            for tool in tool_list:
                if isinstance(tool, dict) and tool.get("name") == tool_name:
                    tool["enabled"] = enabled
                    break

        server.available_tools = tools_data
        await self.db.commit()

        # 返回更新后的工具信息
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
