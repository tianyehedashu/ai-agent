"""MCP Streamable HTTP 门面（生命周期、请求转发、动态资源同步）。"""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import HTTPException, Request
from starlette.responses import Response

from domains.agent.domain.mcp.scopes import MCPServerScope
from domains.agent.infrastructure.mcp_server.auth_middleware import verify_mcp_access
from domains.agent.infrastructure.mcp_server.context import (
    mcp_user_id_var,
    mcp_vendor_creator_id_var,
    set_mcp_user_id,
    set_mcp_vendor_creator_id,
)
from domains.agent.infrastructure.mcp_server.dynamic_prompt_factory import build_prompt
from domains.agent.infrastructure.mcp_server.dynamic_tool_factory import build_tool_fn
from domains.agent.infrastructure.mcp_server.servers import llm_server
from domains.agent.infrastructure.repositories.mcp_dynamic_prompt_repository import (
    MCPDynamicPromptRepository,
)
from domains.agent.infrastructure.repositories.mcp_dynamic_tool_repository import (
    MCPDynamicToolRepository,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

SERVER_MAP = {
    "llm-server": llm_server,
}

_STREAMABLE_HTTP_APPS: dict[str, object] = {}
_initialized = False

_SCOPE_TO_CURSOR_NAME = {
    "llm-server": "ai-agent-llm",
}


def get_mcp_server(server_name: str):
    server = SERVER_MAP.get(server_name)
    if not server:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server not found: {server_name}. "
            f"Available servers: {list(SERVER_MAP.keys())}",
        )
    return server


def _get_streamable_http_app(server_name: str):
    if server_name not in _STREAMABLE_HTTP_APPS:
        server = get_mcp_server(server_name)
        _STREAMABLE_HTTP_APPS[server_name] = server.streamable_http_app()
        logger.debug(
            "Created streamable_http_app for %s (session_manager now available)",
            server_name,
        )
    return _STREAMABLE_HTTP_APPS[server_name]


def ensure_mcp_server_initialized(server_name: str) -> None:
    _get_streamable_http_app(server_name)


def is_mcp_server_initialized(server_name: str) -> bool:
    return server_name in _STREAMABLE_HTTP_APPS


@asynccontextmanager
async def initialize_mcp_servers() -> AsyncIterator[None]:
    global _initialized

    if _initialized:
        logger.warning("MCP servers already initialized, skipping")
        yield
        return

    async with AsyncExitStack() as stack:
        for server_name, mcp_instance in SERVER_MAP.items():
            ensure_mcp_server_initialized(server_name)
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


async def handle_mcp_streamable_request(
    request: Request,
    server_name: str,
    user_id: UUID | None = None,
    vendor_creator_id: int | None = None,
) -> Response:
    token_user = set_mcp_user_id(user_id) if user_id is not None else None
    token_creator = set_mcp_vendor_creator_id(vendor_creator_id)
    try:
        app = _get_streamable_http_app(server_name)
        scope = dict(request.scope)
        scope["path"] = "/mcp"
        if "raw_path" in scope:
            scope["raw_path"] = b"/mcp"

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
        if token_creator is not None:
            mcp_vendor_creator_id_var.reset(token_creator)
        if token_user is not None:
            mcp_user_id_var.reset(token_user)


def scope_to_cursor_name(scope: str) -> str:
    return _SCOPE_TO_CURSOR_NAME.get(scope, scope.replace("-", "_"))


async def sync_dynamic_tools_for_streamable_http(db: AsyncSession) -> None:
    repo = MCPDynamicToolRepository(db)
    for server_name, server in SERVER_MAP.items():
        try:
            rows = await repo.list_by_server("streamable_http", server_name)
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
    repo = MCPDynamicPromptRepository(db)
    for server_name, server in SERVER_MAP.items():
        try:
            rows = await repo.list_by_server("streamable_http", server_name)
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
                except ValueError as e:
                    logger.warning(
                        "Skip dynamic prompt %s on %s: %s",
                        row.prompt_key,
                        server_name,
                        e,
                    )
        except Exception as e:
            logger.warning("Failed to sync dynamic prompts for %s: %s", server_name, e)


async def get_mcp_server_info(db: AsyncSession, server_name: str) -> dict[str, Any]:
    server = get_mcp_server(server_name)
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


async def list_mcp_servers_summary(db: AsyncSession) -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = []
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
    return servers


__all__ = [
    "SERVER_MAP",
    "build_prompt",
    "build_tool_fn",
    "ensure_mcp_server_initialized",
    "get_mcp_server",
    "get_mcp_server_info",
    "handle_mcp_streamable_request",
    "initialize_mcp_servers",
    "is_mcp_server_initialized",
    "list_mcp_servers_summary",
    "scope_to_cursor_name",
    "sync_dynamic_prompts_for_streamable_http",
    "sync_dynamic_tools_for_streamable_http",
    "verify_mcp_access",
]
