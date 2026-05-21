"""
MCP Server Router - MCP 服务器路由

使用 FastMCP 提供 MCP over Streamable HTTP 端点

支持的传输方式:
- Streamable HTTP (推荐，用于 Cursor 等客户端)

重要：FastMCP session_manager 惰性初始化
======================================

FastMCP 的 session_manager 是惰性创建的，必须先调用 streamable_http_app() 才能访问。

错误示例（会抛出 RuntimeError）::

    server = FastMCP("my-server")
    # 直接访问 session_manager 会失败！
    await server.session_manager.run()  # RuntimeError!

正确用法::

    server = FastMCP("my-server")
    # 先调用 streamable_http_app() 初始化
    app = server.streamable_http_app()  # 这会创建 session_manager
    # 然后才能访问 session_manager
    async with server.session_manager.run():
        ...

在应用启动时（lifespan），请使用 initialize_mcp_servers() 函数而不是直接访问 SERVER_MAP。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application.mcp_dynamic_prompt_use_case import (  # noqa: TC001
    MCPDynamicPromptUseCase,
)
from domains.agent.application.mcp_dynamic_tool_use_case import (  # noqa: TC001
    MCPDynamicToolUseCase,
)
from domains.agent.application.mcp_server_facade import (
    SERVER_MAP,
    get_mcp_server_info,
    list_mcp_servers_summary,
)
from domains.agent.application.mcp_server_facade import (
    get_mcp_server as _get_server,
)
from domains.agent.application.mcp_server_facade import (
    handle_mcp_streamable_request as _handle_mcp_request,
)
from domains.agent.application.mcp_server_facade import (
    build_prompt,
    build_tool_fn,
    scope_to_cursor_name as _scope_to_cursor_name,
    verify_mcp_access,
)
from domains.agent.domain.mcp.scopes import MCPServerScope
from domains.identity.presentation.deps import (
    AdminUser,  # noqa: TC001 - required at runtime for FastAPI Depends()
)
from libs.api.deps import (
    get_mcp_dynamic_prompt_service,
    get_mcp_dynamic_tool_service,
    get_user_service,
)
from libs.api.paths import public_api_url
from libs.db.database import get_db
from utils.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.identity.application import UserUseCase

logger = get_logger(__name__)

router = APIRouter()

@router.get("/client-config", include_in_schema=False)
async def mcp_client_config(request: Request):
    """返回 Cursor mcp.json 同构的客户端直连配置（占位 API Key，便于前端复制/下载）"""
    origin = str(request.base_url).rstrip("/")
    mcp_servers: dict = {}
    for server_name in SERVER_MAP:
        try:
            scope = MCPServerScope.from_name(server_name)
            cursor_name = _scope_to_cursor_name(server_name)
            url = public_api_url(origin, "mcp", server_name)
            mcp_servers[cursor_name] = {
                "type": "streamableHttp",
                "url": url,
                "description": MCPServerScope.get_description(scope),
                "headers": {
                    "Authorization": "Bearer <YOUR_API_KEY>",
                },
            }
        except ValueError:
            continue
    return {"mcpServers": mcp_servers}


# 动态工具 API（仅管理员，server_name 须在 SERVER_MAP 中）
class DynamicToolAddBody(BaseModel):
    """添加动态工具请求体"""

    tool_key: str = Field(..., min_length=1, max_length=100)
    tool_type: str = Field(..., min_length=1, max_length=50)
    config: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class DynamicToolUpdateBody(BaseModel):
    """更新动态工具请求体（仅传需修改的字段）"""

    tool_type: str | None = Field(None, min_length=1, max_length=50)
    config: dict[str, Any] | None = None
    description: str | None = None
    enabled: bool | None = None


@router.get("/servers/{server_name}/dynamic-tools", include_in_schema=False)
async def list_dynamic_tools(
    server_name: str,
    _admin: AdminUser,
    use_case: MCPDynamicToolUseCase = Depends(get_mcp_dynamic_tool_service),
) -> list[dict]:
    """列出某客户端直连 MCP 的动态工具（仅管理员）"""
    _get_server(server_name)  # 404 if not in SERVER_MAP
    return await use_case.list_dynamic_tools(server_name)


@router.post("/servers/{server_name}/dynamic-tools", status_code=201, include_in_schema=False)
async def add_dynamic_tool(
    server_name: str,
    body: DynamicToolAddBody,
    _admin: AdminUser,
    use_case: MCPDynamicToolUseCase = Depends(get_mcp_dynamic_tool_service),
) -> dict:
    """添加一条动态工具并注册到 FastMCP（仅管理员）"""
    server = _get_server(server_name)
    record = await use_case.add_dynamic_tool(
        server_name=server_name,
        tool_key=body.tool_key.strip(),
        tool_type=body.tool_type,
        config=body.config,
        description=body.description,
    )
    try:
        fn = build_tool_fn(body.tool_type, body.config)
        server.add_tool(
            fn,
            name=body.tool_key.strip(),
            description=body.description or "",
        )
    except ValueError as e:
        logger.warning("Failed to register dynamic tool with FastMCP: %s", e)
    return record


@router.put(
    "/servers/{server_name}/dynamic-tools/{tool_key}",
    include_in_schema=False,
)
async def update_dynamic_tool(
    server_name: str,
    tool_key: str,
    body: DynamicToolUpdateBody,
    _admin: AdminUser,
    use_case: MCPDynamicToolUseCase = Depends(get_mcp_dynamic_tool_service),
) -> dict:
    """更新一条动态工具并同步到 FastMCP（仅管理员）"""
    server = _get_server(server_name)
    updates = body.model_dump(exclude_unset=True)
    record = await use_case.update_dynamic_tool(server_name, tool_key, **updates)
    try:
        server.remove_tool(tool_key)
    except Exception as e:
        logger.warning("Failed to remove old tool from FastMCP: %s", e)
    tool_type = record["tool_type"]
    config = record["config"] or {}
    if record.get("enabled", True):
        try:
            fn = build_tool_fn(tool_type, config)
            server.add_tool(
                fn,
                name=record["tool_key"],
                description=record["description"] or "",
            )
        except ValueError as e:
            logger.warning("Failed to re-register dynamic tool with FastMCP: %s", e)
    return record


@router.delete(
    "/servers/{server_name}/dynamic-tools/{tool_key}",
    status_code=204,
    include_in_schema=False,
)
async def delete_dynamic_tool(
    server_name: str,
    tool_key: str,
    _admin: AdminUser,
    use_case: MCPDynamicToolUseCase = Depends(get_mcp_dynamic_tool_service),
) -> None:
    """删除一条动态工具并从 FastMCP 移除（仅管理员）"""
    server = _get_server(server_name)
    await use_case.remove_dynamic_tool(server_name, tool_key)
    try:
        server.remove_tool(tool_key)
    except Exception as e:
        logger.warning("Failed to remove tool from FastMCP: %s", e)


# 动态 Prompt API（仅管理员）
class DynamicPromptAddBody(BaseModel):
    """添加动态 Prompt 请求体"""

    prompt_key: str = Field(..., min_length=1, max_length=100)
    template: str = Field(..., min_length=1)
    title: str | None = Field(None, max_length=200)
    description: str | None = None
    arguments_schema: list[dict[str, Any]] = Field(default_factory=list)


class DynamicPromptUpdateBody(BaseModel):
    """更新动态 Prompt 请求体（仅传需修改的字段）"""

    template: str | None = Field(None, min_length=1)
    title: str | None = Field(None, max_length=200)
    description: str | None = None
    arguments_schema: list[dict[str, Any]] | None = None
    enabled: bool | None = None


@router.get("/servers/{server_name}/dynamic-prompts", include_in_schema=False)
async def list_dynamic_prompts(
    server_name: str,
    _admin: AdminUser,
    use_case: MCPDynamicPromptUseCase = Depends(get_mcp_dynamic_prompt_service),
) -> list[dict]:
    """列出某客户端直连 MCP 的动态 Prompts（仅管理员）"""
    _get_server(server_name)
    return await use_case.list_dynamic_prompts(server_name)


@router.post("/servers/{server_name}/dynamic-prompts", status_code=201, include_in_schema=False)
async def add_dynamic_prompt(
    server_name: str,
    body: DynamicPromptAddBody,
    _admin: AdminUser,
    use_case: MCPDynamicPromptUseCase = Depends(get_mcp_dynamic_prompt_service),
) -> dict:
    """添加一条动态 Prompt 并注册到 FastMCP（仅管理员）"""
    server = _get_server(server_name)
    record = await use_case.add_dynamic_prompt(
        server_name=server_name,
        prompt_key=body.prompt_key.strip(),
        template=body.template.strip(),
        title=body.title.strip() if body.title else None,
        description=body.description.strip() if body.description else None,
        arguments_schema=body.arguments_schema,
    )
    try:
        prompt_obj = build_prompt(
            name=record["prompt_key"],
            template=record["template"],
            title=record.get("title"),
            description=record.get("description"),
            arguments_schema=record.get("arguments_schema") or [],
        )
        server.add_prompt(prompt_obj)
        logger.debug("Registered dynamic prompt %s on %s", record["prompt_key"], server_name)
    except ValueError as e:
        logger.warning("Failed to register dynamic prompt with FastMCP: %s", e)
    return record


@router.put(
    "/servers/{server_name}/dynamic-prompts/{prompt_key}",
    include_in_schema=False,
)
async def update_dynamic_prompt(
    server_name: str,
    prompt_key: str,
    body: DynamicPromptUpdateBody,
    _admin: AdminUser,
    use_case: MCPDynamicPromptUseCase = Depends(get_mcp_dynamic_prompt_service),
) -> dict:
    """更新一条动态 Prompt 并同步到 FastMCP（仅管理员）"""
    server = _get_server(server_name)
    updates = body.model_dump(exclude_unset=True)
    record = await use_case.update_dynamic_prompt(server_name, prompt_key, **updates)
    try:
        prompt_obj = build_prompt(
            name=record["prompt_key"],
            template=record["template"],
            title=record.get("title"),
            description=record.get("description"),
            arguments_schema=record.get("arguments_schema") or [],
        )
        server.add_prompt(prompt_obj)
        logger.debug("Re-registered dynamic prompt %s on %s", record["prompt_key"], server_name)
    except ValueError as e:
        logger.warning("Failed to re-register dynamic prompt with FastMCP: %s", e)
    return record


@router.delete(
    "/servers/{server_name}/dynamic-prompts/{prompt_key}",
    status_code=204,
    include_in_schema=False,
)
async def delete_dynamic_prompt(
    server_name: str,
    prompt_key: str,
    _admin: AdminUser,
    use_case: MCPDynamicPromptUseCase = Depends(get_mcp_dynamic_prompt_service),
) -> None:
    """删除一条动态 Prompt（仅管理员）。注：FastMCP 无 remove_prompt，需重启后该 prompt 才从 MCP 协议中消失。"""
    _get_server(server_name)
    await use_case.remove_dynamic_prompt(server_name, prompt_key)


@router.api_route(
    "/{server_name}",
    methods=["GET", "POST", "DELETE"],
    include_in_schema=False,
)
async def mcp_streamable_http_endpoint(
    request: Request,
    server_name: str,
    auth_result: tuple[UUID, UUID, set, str | None] = Depends(verify_mcp_access),
    db: AsyncSession = Depends(get_db),
    user_use_case: UserUseCase = Depends(get_user_service),
):
    """MCP Streamable HTTP 端点

    符合 MCP Streamable HTTP 规范:
    - GET: 获取 SSE 事件流
    - POST: 发送 JSON-RPC 请求
    - DELETE: 终止会话

    认证通过后从 identity 应用层解析当前用户的 vendor_creator_id，写入 MCP context，
    供下游工具（如视频任务）与 Web 端行为一致。
    """
    api_key_id, user_id, _scopes, client_ip = auth_result

    vendor_creator_id: int | None = None
    if user_id is not None:
        user = await user_use_case.get_user_by_id(str(user_id))
        vendor_creator_id = user.vendor_creator_id if user else None

    logger.info(
        "MCP Streamable HTTP request: method=%s, server=%s, api_key_id=%s, user_id=%s, client_ip=%s",
        request.method,
        server_name,
        api_key_id,
        user_id,
        client_ip,
    )

    return await _handle_mcp_request(request, server_name, user_id, vendor_creator_id)


@router.get("/{server_name}/info", include_in_schema=False)
async def mcp_server_info(
    server_name: str,
    _auth: tuple = Depends(verify_mcp_access),
    db: AsyncSession = Depends(get_db),
):
    """获取 MCP 服务器信息"""
    return await get_mcp_server_info(db, server_name)


@router.get("/", include_in_schema=False)
async def mcp_servers_list(db: AsyncSession = Depends(get_db)):
    """列出所有可用的 MCP 服务器（含工具与 Prompts 列表）"""
    servers = await list_mcp_servers_summary(db)
    return {
        "servers": servers,
        "transport": "Streamable HTTP",
        "authentication": "API Key (Bearer sk_...)",
        "protocol_version": "2024-11-05",
    }
