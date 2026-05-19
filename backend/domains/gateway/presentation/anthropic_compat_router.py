"""
Anthropic Messages API 兼容入口（挂载在根路径 /v1）

提供 ``POST /v1/messages``（含 SSE），鉴权与 OpenAI 兼容面一致：
``Authorization: Bearer`` 或 ``x-api-key``（虚拟 Key / gateway:proxy 的 sk-）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
import orjson
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.proxy_use_case import ProxyUseCase
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.presentation.deps import (
    VkeyOrApikeyPrincipal,
    bearer_vkey_or_apikey_auth,
)
from domains.gateway.presentation.gateway_proxy_business_error_classify import (
    classify_proxy_use_case_business_error,
)
from domains.gateway.presentation.gateway_proxy_context import (
    proxy_context_from_gateway_principal,
)
from libs.db.database import get_db
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["Anthropic Compat"])


def _anthropic_error(
    *,
    http_status: int,
    error_type: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"type": "error", "error": {"type": error_type, "message": message}},
    )


def _wrap_anthropic_business_errors(exc: Exception) -> HTTPException:
    classified = classify_proxy_use_case_business_error(exc)
    if classified is not None:
        headers = (
            {"Retry-After": str(classified.retry_after)}
            if classified.retry_after is not None
            else None
        )
        return HTTPException(
            status_code=classified.http_status,
            detail={
                "type": "error",
                "error": {
                    "type": classified.anthropic_error_type,
                    "message": classified.message,
                },
            },
            headers=headers,
        )
    return _anthropic_error(
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type="api_error",
        message=str(exc),
    )


@router.post("/messages")
async def create_message(
    body: dict[str, Any],
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Anthropic ``Messages``：LiteLLM ``anthropic_unified`` 原生通道。"""
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.CHAT)

    try:
        result = await use_case.anthropic_messages(ctx, body)
    except ValueError as exc:
        raise _wrap_anthropic_business_errors(exc) from exc
    except Exception as exc:
        logger.warning("anthropic messages failed: %s", exc)
        raise _wrap_anthropic_business_errors(exc) from exc

    if body.get("stream"):
        stream = cast("AsyncIterator[bytes]", result)

        async def _sse() -> AsyncIterator[bytes]:
            async for part in stream:
                yield part

        return StreamingResponse(
            _sse(),
            media_type="text/event-stream; charset=utf-8",
        )

    if not isinstance(result, dict):
        raise _anthropic_error(
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="api_error",
            message="Unexpected response shape",
        )
    return Response(
        content=orjson.dumps(result),
        media_type="application/json",
    )


__all__ = ["router"]
