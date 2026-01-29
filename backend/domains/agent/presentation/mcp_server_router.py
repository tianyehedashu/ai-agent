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
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response

from domains.agent.domain.mcp.scopes import MCPServerScope
from domains.agent.infrastructure.mcp_server.auth_middleware import verify_mcp_access
from domains.agent.infrastructure.mcp_server.servers import llm_server
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

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


async def _handle_mcp_request(request: Request, server_name: str, user_id: UUID | None = None):
    """处理 MCP Streamable HTTP 请求

    将请求转发给 FastMCP 的 Streamable HTTP 应用。
    若有 user_id 则通过 contextvar 传入，供 MCP 工具（如 LLM）使用。
    """
    from domains.agent.infrastructure.mcp_server.context import set_mcp_user_id

    token = set_mcp_user_id(user_id) if user_id else None
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
        if token is not None:
            from domains.agent.infrastructure.mcp_server.context import (
                mcp_user_id_var,
            )

            mcp_user_id_var.reset(token)


@router.api_route(
    "/{server_name}",
    methods=["GET", "POST", "DELETE"],
    include_in_schema=False,
)
async def mcp_streamable_http_endpoint(
    request: Request,
    server_name: str,
    auth_result: tuple[UUID, UUID, set, str | None] = Depends(verify_mcp_access),
):
    """MCP Streamable HTTP 端点

    符合 MCP Streamable HTTP 规范:
    - GET: 获取 SSE 事件流
    - POST: 发送 JSON-RPC 请求
    - DELETE: 终止会话
    """
    api_key_id, user_id, _scopes, client_ip = auth_result

    logger.info(
        "MCP Streamable HTTP request: method=%s, server=%s, api_key_id=%s, user_id=%s, client_ip=%s",
        request.method,
        server_name,
        api_key_id,
        user_id,
        client_ip,
    )

    return await _handle_mcp_request(request, server_name, user_id)


@router.get("/{server_name}/info", include_in_schema=False)
async def mcp_server_info(
    server_name: str,
    _auth: tuple = Depends(verify_mcp_access),
):
    """获取 MCP 服务器信息"""
    server = _get_server(server_name)
    # FastMCP 未提供公开的 list_tools API，仅能通过 _tool_manager 获取工具列表
    tools = server._tool_manager.list_tools() if hasattr(server, "_tool_manager") else []  # pylint: disable=protected-access

    return {
        "name": server.name,
        "scope": server_name,
        "description": MCPServerScope.get_description(MCPServerScope.from_name(server_name)),
        "tool_count": len(tools),
        "tools": [{"name": t.name, "description": t.description} for t in tools] if tools else [],
        "transport": "Streamable HTTP",
        "protocol_version": "2024-11-05",
    }


@router.get("/", include_in_schema=False)
async def mcp_servers_list():
    """列出所有可用的 MCP 服务器"""
    servers = []

    for server_name, server in SERVER_MAP.items():
        try:
            scope = MCPServerScope.from_name(server_name)
            # FastMCP 未提供公开的 list_tools API，仅能通过 _tool_manager 获取
            tools = server._tool_manager.list_tools() if hasattr(server, "_tool_manager") else []  # pylint: disable=protected-access
            servers.append(
                {
                    "name": server.name,
                    "scope": server_name,
                    "description": MCPServerScope.get_description(scope),
                    "tool_count": len(tools),
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
