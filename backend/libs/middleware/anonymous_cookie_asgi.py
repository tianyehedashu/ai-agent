"""
匿名用户 Cookie（纯 ASGI）

与 StreamingResponse 兼容；避免 BaseHTTPMiddleware 在流未结束即取消内部任务。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.datastructures import MutableHeaders
from starlette.responses import Response

from bootstrap.config import settings

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send

ANONYMOUS_USER_COOKIE = "anonymous_user_id"
ANONYMOUS_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 年


class AnonymousCookieASGIMiddleware:
    """检测 ``scope["state"]["anonymous_user_id"]`` 并在 ``http.response.start`` 附加 Set-Cookie。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                state = scope.get("state")
                anonymous_id: str | None = None
                if isinstance(state, dict):
                    anonymous_id = state.get("anonymous_user_id")
                elif state is not None:
                    anonymous_id = getattr(state, "anonymous_user_id", None)
                if anonymous_id:
                    cookie_response = Response()
                    cookie_response.set_cookie(
                        key=ANONYMOUS_USER_COOKIE,
                        value=str(anonymous_id),
                        max_age=ANONYMOUS_COOKIE_MAX_AGE,
                        path="/",
                        httponly=True,
                        samesite="lax",
                        secure=settings.is_cookie_secure,
                    )
                    headers = MutableHeaders(scope=message)
                    for header_key, header_val in cookie_response.raw_headers:
                        if header_key.lower() == b"set-cookie":
                            headers.append("set-cookie", header_val.decode("latin-1"))
            await send(message)

        await self.app(scope, receive, send_wrapper)


__all__ = [
    "ANONYMOUS_COOKIE_MAX_AGE",
    "ANONYMOUS_USER_COOKIE",
    "AnonymousCookieASGIMiddleware",
]
