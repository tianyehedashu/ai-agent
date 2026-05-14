"""
Anthropic Messages API 兼容入口（挂载在根路径 /v1）

提供 ``POST /v1/messages``（含 SSE），鉴权与 OpenAI 兼容面一致：
``Authorization: Bearer`` 或 ``x-api-key``（虚拟 Key / gateway:proxy 的 sk-）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any, cast
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
import orjson
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.anthropic_openai_bridge import (
    anthropic_messages_request_to_openai_chat,
    openai_chat_completion_response_to_anthropic_message,
    openai_chat_stream_chunks_to_anthropic_sse,
)
from domains.gateway.application.proxy_use_case import ProxyUseCase
from domains.gateway.domain.errors import (
    BudgetExceededError,
    CapabilityNotAllowedError,
    GuardrailBlockedError,
    ModelNotAllowedError,
    RateLimitExceededError,
)
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.presentation.deps import (
    VkeyOrApikeyPrincipal,
    bearer_vkey_or_apikey_auth,
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
    if isinstance(exc, ModelNotAllowedError):
        return _anthropic_error(
            http_status=status.HTTP_400_BAD_REQUEST,
            error_type="invalid_request_error",
            message=str(exc),
        )
    if isinstance(exc, CapabilityNotAllowedError):
        return _anthropic_error(
            http_status=status.HTTP_400_BAD_REQUEST,
            error_type="invalid_request_error",
            message=str(exc),
        )
    if isinstance(exc, RateLimitExceededError):
        return _anthropic_error(
            http_status=status.HTTP_429_TOO_MANY_REQUESTS,
            error_type="rate_limit_error",
            message=str(exc),
        )
    if isinstance(exc, BudgetExceededError):
        return _anthropic_error(
            http_status=status.HTTP_402_PAYMENT_REQUIRED,
            error_type="api_error",
            message=str(exc),
        )
    if isinstance(exc, GuardrailBlockedError):
        return _anthropic_error(
            http_status=status.HTTP_400_BAD_REQUEST,
            error_type="invalid_request_error",
            message=str(exc),
        )
    if isinstance(exc, ValueError):
        return _anthropic_error(
            http_status=status.HTTP_400_BAD_REQUEST,
            error_type="invalid_request_error",
            message=str(exc),
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
    """Anthropic ``Messages``：经 OpenAI 形 body 复用 ``ProxyUseCase.chat_completion``。"""
    try:
        openai_body = anthropic_messages_request_to_openai_chat(body)
    except ValueError as exc:
        raise _wrap_anthropic_business_errors(exc) from exc

    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.CHAT)

    try:
        result = await use_case.chat_completion(ctx, openai_body)
    except Exception as exc:
        logger.warning("anthropic messages failed: %s", exc)
        raise _wrap_anthropic_business_errors(exc) from exc

    if openai_body.get("stream"):
        stream = cast("AsyncIterator[dict[str, Any]]", result)
        message_id = f"msg_{uuid.uuid4().hex}"
        model = str(body.get("model", "")).strip()

        async def _sse() -> AsyncIterator[bytes]:
            async for part in openai_chat_stream_chunks_to_anthropic_sse(
                stream,
                model=model,
                message_id=message_id,
            ):
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
    try:
        anthropic_body = openai_chat_completion_response_to_anthropic_message(result)
    except ValueError as exc:
        raise _wrap_anthropic_business_errors(exc) from exc
    return Response(
        content=orjson.dumps(anthropic_body),
        media_type="application/json",
    )


__all__ = ["router"]
