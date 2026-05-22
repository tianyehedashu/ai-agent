"""Gateway 平台 API Key 使用日志回写中间件（纯 ASGI，兼容 SSE）。"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING

from utils.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = get_logger(__name__)

PLATFORM_API_KEY_USAGE_STATE = "platform_api_key_usage"


@dataclass(frozen=True, slots=True)
class PlatformApiKeyUsageContext:
    """请求级平台 API Key 上下文，供代理完成后回写 Identity 使用日志。"""

    api_key_id: uuid.UUID
    user_id: uuid.UUID


class PlatformApiKeyUsageASGIMiddleware:
    """在 /v1/* 代理响应后回写平台 sk-* 的使用统计。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        ctx = scope.get(PLATFORM_API_KEY_USAGE_STATE)
        if ctx is None:
            state = scope.get("state")
            ctx = getattr(state, PLATFORM_API_KEY_USAGE_STATE, None) if state is not None else None
        if ctx is None:
            return

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        client = scope.get("client")
        client_ip = client[0] if client else None
        user_agent: str | None = None
        for name, value in scope.get("headers") or []:
            if name.lower() == b"user-agent":
                user_agent = value.decode("latin-1")
                break
        path = scope.get("path", "")

        try:
            from libs.db.database import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                from domains.gateway.application.gateway_access_factory import (
                    build_gateway_access_use_case,
                )

                access = build_gateway_access_use_case(session)
                await access.record_platform_api_key_usage(
                    ctx.api_key_id,
                    user_id=ctx.user_id,
                    endpoint=path,
                    method=scope.get("method", "GET"),
                    ip_address=client_ip,
                    user_agent=user_agent,
                    status_code=status_code,
                    response_time_ms=elapsed_ms,
                )
                await session.commit()
        except Exception:
            logger.exception(
                "Failed to record platform API key usage for %s",
                ctx.api_key_id,
            )


__all__ = [
    "PLATFORM_API_KEY_USAGE_STATE",
    "PlatformApiKeyUsageASGIMiddleware",
    "PlatformApiKeyUsageContext",
]
