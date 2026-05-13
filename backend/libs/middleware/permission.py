"""
Permission Context Middleware - 权限上下文中间件

在请求边界预清与清理权限上下文（ContextVar），避免跨请求泄漏。

实际权限上下文由认证依赖（如 get_current_user）在解析身份后调用 set_permission_context。

提供纯 ASGI 实现，与 StreamingResponse 兼容（避免 BaseHTTPMiddleware 流式取消竞态）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from libs.db.permission_context import clear_permission_context, set_permission_context

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class PermissionContextASGIMiddleware:
    """预清并在整段 ASGI 调用结束后清理权限 ContextVar。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            set_permission_context(None)
            await self.app(scope, receive, send)
        finally:
            clear_permission_context()


__all__ = ["PermissionContextASGIMiddleware"]
