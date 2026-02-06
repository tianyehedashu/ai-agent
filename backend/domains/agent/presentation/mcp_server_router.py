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

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from domains.agent.application.mcp_dynamic_prompt_use_case import (  # noqa: TC001
    MCPDynamicPromptUseCase,
)
from domains.agent.application.mcp_dynamic_tool_use_case import (  # noqa: TC001
    MCPDynamicToolUseCase,
)
from domains.agent.domain.mcp.scopes import MCPServerScope
from domains.agent.infrastructure.mcp_server.auth_middleware import verify_mcp_access
from domains.agent.infrastructure.mcp_server.dynamic_prompt_factory import build_prompt
from domains.agent.infrastructure.mcp_server.dynamic_tool_factory import build_tool_fn
from domains.agent.infrastructure.mcp_server.servers import llm_server
from domains.agent.infrastructure.repositories.mcp_dynamic_prompt_repository import (
    MCPDynamicPromptRepository,
)
from domains.agent.infrastructure.repositories.mcp_dynamic_tool_repository import (
    MCPDynamicToolRepository,
)
from domains.identity.application import UserUseCase
from domains.identity.presentation.deps import (
    AdminUser,  # noqa: TC001 - required at runtime for FastAPI Depends()
)
from libs.api.deps import (
    get_mcp_dynamic_prompt_service,
    get_mcp_dynamic_tool_service,
    get_user_service,
)
from libs.db.database import get_db
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

router = APIRouter()

# 服务器映射：server_name -> FastMCP 实例
SERVER_MAP = {
    "llm-server": llm_server,
}

# 缓存 Streamable HTTP 应用实例
_STREAMABLE_HTTP_APPS: dict = {}

# 标记是否已初始化（用于防止重复初始化和检测未初始化访问）
_initialized = False


def _get_server(server_name: str):
    """获取 FastMCP 服务器实例"""
    server = SERVER_MAP.get(server_name)
    if not server:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server not found: {server_name}. "
            f"Available servers: {list(SERVER_MAP.keys())}",
        )
    return server


def _get_streamable_http_app(server_name: str):
    """获取或创建 Streamable HTTP 应用

    注意：此函数会触发 streamable_http_app() 调用，从而创建 session_manager。
    在应用启动时，应通过 initialize_mcp_servers() 统一初始化所有服务器。
    """
    if server_name not in _STREAMABLE_HTTP_APPS:
        server = _get_server(server_name)
        # 调用 streamable_http_app() 会创建 session_manager
        # 这是 FastMCP 的设计：session_manager 是惰性创建的
        _STREAMABLE_HTTP_APPS[server_name] = server.streamable_http_app()
        logger.debug(
            "Created streamable_http_app for %s (session_manager now available)",
            server_name,
        )
    return _STREAMABLE_HTTP_APPS[server_name]


def ensure_initialized(server_name: str) -> None:
    """确保指定服务器的 streamable_http_app 已初始化

    在访问 session_manager 之前必须调用此函数或 _get_streamable_http_app。

    Args:
        server_name: 服务器名称

    Raises:
        HTTPException: 如果服务器不存在
    """
    _get_streamable_http_app(server_name)


def is_server_initialized(server_name: str) -> bool:
    """检查服务器是否已初始化

    Args:
        server_name: 服务器名称

    Returns:
        bool: True 如果已初始化，False 否则
    """
    return server_name in _STREAMABLE_HTTP_APPS


@asynccontextmanager
async def initialize_mcp_servers() -> AsyncIterator[None]:
    """初始化所有 MCP 服务器并管理其生命周期

    这是在应用启动时初始化 MCP 服务器的推荐方式。
    它会：
    1. 为每个服务器调用 streamable_http_app() 创建 session_manager
    2. 启动所有 session_manager
    3. 在退出时清理资源

    用法（在 FastAPI lifespan 中）::

        from domains.agent.presentation.mcp_server_router import initialize_mcp_servers


        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with initialize_mcp_servers():
                yield

    Yields:
        None

    Raises:
        RuntimeError: 如果初始化失败
    """
    global _initialized  # pylint: disable=global-statement

    from contextlib import AsyncExitStack

    if _initialized:
        logger.warning("MCP servers already initialized, skipping")
        yield
        return

    async with AsyncExitStack() as stack:
        for server_name, mcp_instance in SERVER_MAP.items():
            # 步骤 1: 先调用 streamable_http_app() 创建 session_manager
            # 这是 FastMCP 的要求：session_manager 是惰性创建的
            ensure_initialized(server_name)
            logger.debug("Initialized streamable_http_app for %s", server_name)

            # 步骤 2: 然后才能安全地访问 session_manager.run()
            await stack.enter_async_context(mcp_instance.session_manager.run())
            logger.debug("Started session_manager for %s", server_name)

        _initialized = True
        logger.info(
            "MCP Streamable HTTP session managers started for %d servers",
            len(SERVER_MAP),
        )

        yield

    _initialized = False
    logger.info("MCP Streamable HTTP session managers stopped")


async def _handle_mcp_request(
    request: Request,
    server_name: str,
    user_id: UUID | None = None,
    vendor_creator_id: int | None = None,
):
    """处理 MCP Streamable HTTP 请求

    将请求转发给 FastMCP 的 Streamable HTTP 应用。
    若有 user_id / vendor_creator_id 则通过 contextvar 传入，供 MCP 工具（如 LLM、视频任务）使用。
    """
    from domains.agent.infrastructure.mcp_server.context import (
        set_mcp_user_id,
        set_mcp_vendor_creator_id,
    )

    token_user = set_mcp_user_id(user_id) if user_id is not None else None
    token_creator = set_mcp_vendor_creator_id(vendor_creator_id)
    try:
        app = _get_streamable_http_app(server_name)

        # 修改 scope 中的路径：FastMCP streamable_http_app 只认 /mcp
        # 无论挂载在 /api/v1/mcp 还是 /mcp，转发时都传 /mcp
        scope = dict(request.scope)
        scope["path"] = "/mcp"
        if "raw_path" in scope:
            scope["raw_path"] = b"/mcp"

        # 收集响应
        response_status = 200
        response_headers: list[tuple[bytes, bytes]] = []
        response_body = bytearray()

        async def receive():
            return await request.receive()

        async def send(message):
            nonlocal response_status, response_headers, response_body
            if message["type"] == "http.response.start":
                response_status = message.get("status", 200)
                response_headers = message.get("headers", [])
            elif message["type"] == "http.response.body":
                if body := message.get("body", b""):
                    response_body.extend(body)

        await app(scope, receive, send)

        headers_dict = {k.decode(): v.decode() for k, v in response_headers}
        return Response(
            content=bytes(response_body),
            status_code=response_status,
            headers=headers_dict,
            media_type=headers_dict.get("content-type", "application/json"),
        )
    finally:
        from domains.agent.infrastructure.mcp_server.context import (
            mcp_user_id_var,
            mcp_vendor_creator_id_var,
        )

        if token_creator is not None:
            mcp_vendor_creator_id_var.reset(token_creator)
        if token_user is not None:
            mcp_user_id_var.reset(token_user)


# Cursor mcp.json 中常用的客户端显示名（scope -> 显示名）
_SCOPE_TO_CURSOR_NAME = {
    "llm-server": "ai-agent-llm",
}


def _scope_to_cursor_name(scope: str) -> str:
    """将后端 scope 转为 Cursor mcp.json 中常用的 key（如 ai-agent-llm）"""
    return _SCOPE_TO_CURSOR_NAME.get(scope, scope.replace("-", "_"))


@router.get("/client-config", include_in_schema=False)
async def mcp_client_config(request: Request):
    """返回 Cursor mcp.json 同构的客户端直连配置（占位 API Key，便于前端复制/下载）"""
    base_url = str(request.base_url).rstrip("/")
    # 使用 /api/v1/mcp 前缀与 main 中挂载一致
    if "/api/v1" not in base_url:
        base_url = f"{base_url}/api/v1"
    mcp_servers: dict = {}
    for server_name in SERVER_MAP:
        try:
            scope = MCPServerScope.from_name(server_name)
            cursor_name = _scope_to_cursor_name(server_name)
            url = f"{base_url}/mcp/{server_name}"
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
    try:
        record = await use_case.add_dynamic_tool(
            server_name=server_name,
            tool_key=body.tool_key.strip(),
            tool_type=body.tool_type,
            config=body.config,
            description=body.description,
        )
    except Exception:
        raise
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
    server = _get_server(server_name)
    tools = server._tool_manager.list_tools() if hasattr(server, "_tool_manager") else []  # pylint: disable=protected-access
    prompt_repo = MCPDynamicPromptRepository(db)
    prompt_rows = await prompt_repo.list_by_server("streamable_http", server_name)
    prompts = [
        {"name": r.prompt_key, "title": r.title or r.prompt_key, "description": r.description or ""}
        for r in prompt_rows
        if r.enabled
    ]
    return {
        "name": server.name,
        "scope": server_name,
        "description": MCPServerScope.get_description(MCPServerScope.from_name(server_name)),
        "tool_count": len(tools),
        "tools": [{"name": t.name, "description": t.description} for t in tools] if tools else [],
        "prompt_count": len(prompts),
        "prompts": prompts,
        "transport": "Streamable HTTP",
        "protocol_version": "2024-11-05",
    }


@router.get("/", include_in_schema=False)
async def mcp_servers_list(db: AsyncSession = Depends(get_db)):
    """列出所有可用的 MCP 服务器（含工具与 Prompts 列表）"""
    servers = []
    prompt_repo = MCPDynamicPromptRepository(db)
    for server_name, server in SERVER_MAP.items():
        try:
            scope = MCPServerScope.from_name(server_name)
            tools = server._tool_manager.list_tools() if hasattr(server, "_tool_manager") else []  # pylint: disable=protected-access
            prompt_rows = await prompt_repo.list_by_server("streamable_http", server_name)
            prompts = [
                {
                    "name": r.prompt_key,
                    "title": r.title or r.prompt_key,
                    "description": r.description or "",
                }
                for r in prompt_rows
                if r.enabled
            ]
            servers.append(
                {
                    "name": server.name,
                    "scope": server_name,
                    "description": MCPServerScope.get_description(scope),
                    "tool_count": len(tools),
                    "tools": [
                        {"name": t.name, "description": getattr(t, "description", None) or ""}
                        for t in tools
                    ],
                    "prompt_count": len(prompts),
                    "prompts": prompts,
                }
            )
        except ValueError:
            continue

    return {
        "servers": servers,
        "transport": "Streamable HTTP",
        "authentication": "API Key (Bearer sk_...)",
        "protocol_version": "2024-11-05",
    }


async def sync_dynamic_tools_for_streamable_http(db: AsyncSession) -> None:
    """启动时将 DB 中已配置的动态工具注册到各 FastMCP 实例"""
    repo = MCPDynamicToolRepository(db)
    for server_name in SERVER_MAP:
        try:
            rows = await repo.list_by_server("streamable_http", server_name)
            server = SERVER_MAP[server_name]
            for row in rows:
                if not row.enabled:
                    continue
                try:
                    fn = build_tool_fn(row.tool_type, row.config_json or {})
                    server.add_tool(
                        fn,
                        name=row.tool_key,
                        description=row.description or "",
                    )
                    logger.debug("Registered dynamic tool %s on %s", row.tool_key, server_name)
                except ValueError as e:
                    logger.warning(
                        "Skip dynamic tool %s on %s: %s",
                        row.tool_key,
                        server_name,
                        e,
                    )
        except Exception as e:
            logger.warning("Failed to sync dynamic tools for %s: %s", server_name, e)


async def sync_dynamic_prompts_for_streamable_http(db: AsyncSession) -> None:
    """启动时将 DB 中已配置的动态 Prompts 注册到各 FastMCP 实例"""
    repo = MCPDynamicPromptRepository(db)
    for server_name in SERVER_MAP:
        try:
            rows = await repo.list_by_server("streamable_http", server_name)
            server = SERVER_MAP[server_name]
            for row in rows:
                if not row.enabled:
                    continue
                try:
                    prompt_obj = build_prompt(
                        name=row.prompt_key,
                        template=row.template,
                        title=row.title,
                        description=row.description,
                        arguments_schema=row.arguments_schema or [],
                    )
                    server.add_prompt(prompt_obj)
                    logger.debug("Registered dynamic prompt %s on %s", row.prompt_key, server_name)
                except ValueError as e:
                    logger.warning(
                        "Skip dynamic prompt %s on %s: %s",
                        row.prompt_key,
                        server_name,
                        e,
                    )
        except Exception as e:
            logger.warning("Failed to sync dynamic prompts for %s: %s", server_name, e)
