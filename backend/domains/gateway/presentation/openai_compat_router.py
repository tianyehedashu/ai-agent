"""
OpenAI 兼容入口（挂载在根路径 /）

提供：
- POST /v1/chat/completions（含 SSE）
- POST /v1/embeddings
- POST /v1/images/generations
- POST /v1/audio/transcriptions
- POST /v1/audio/speech
- POST /v1/rerank
- GET  /v1/models
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
import orjson
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.management import GatewayManagementReadService
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

router = APIRouter(prefix="/v1", tags=["OpenAI Compat"])


def _wrap_business_errors(exc: Exception) -> HTTPException:
    """把领域异常转成 OpenAI 兼容的 HTTP 错误"""
    if isinstance(exc, ModelNotAllowedError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"type": "model_not_allowed", "message": str(exc)}},
        )
    if isinstance(exc, CapabilityNotAllowedError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"type": "capability_not_allowed", "message": str(exc)}},
        )
    if isinstance(exc, RateLimitExceededError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"type": "rate_limit_exceeded", "message": str(exc)}},
            headers=({"Retry-After": str(exc.retry_after)} if exc.retry_after else None),
        )
    if isinstance(exc, BudgetExceededError):
        return HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": {"type": "budget_exceeded", "message": str(exc)}},
        )
    if isinstance(exc, GuardrailBlockedError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"type": "guardrail_blocked", "message": str(exc)}},
        )
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"type": "invalid_request", "message": str(exc)}},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": {"type": "server_error", "message": str(exc)}},
    )


# =============================================================================
# /v1/chat/completions
# =============================================================================


@router.post("/chat/completions")
async def chat_completions(
    body: dict[str, Any],
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.CHAT)
    try:
        result = await use_case.chat_completion(ctx, body)
    except Exception as exc:
        logger.warning("chat_completions failed: %s", exc)
        raise _wrap_business_errors(exc) from exc

    if body.get("stream"):

        async def _sse() -> AsyncIterator[bytes]:
            async for chunk in result:  # type: ignore[union-attr]
                yield b"data: " + orjson.dumps(chunk) + b"\n\n"
            yield b"data: [DONE]\n\n"

        return StreamingResponse(_sse(), media_type="text/event-stream")
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/embeddings
# =============================================================================


@router.post("/embeddings")
async def embeddings(
    body: dict[str, Any],
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.EMBEDDING)
    try:
        result = await use_case.embedding(ctx, body)
    except Exception as exc:
        raise _wrap_business_errors(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/images/generations
# =============================================================================


@router.post("/images/generations")
async def image_generations(
    body: dict[str, Any],
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.IMAGE)
    try:
        result = await use_case.image_generation(ctx, body)
    except Exception as exc:
        raise _wrap_business_errors(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/audio/transcriptions
# =============================================================================


@router.post("/audio/transcriptions")
async def audio_transcriptions(
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    model: str = Form(...),
    language: str | None = Form(default=None),
    prompt: str | None = Form(default=None),
    response_format: str | None = Form(default=None),
    temperature: float | None = Form(default=None),
) -> Response:
    contents = await file.read()
    body: dict[str, Any] = {
        "file": (file.filename or "audio", contents, file.content_type),
        "model": model,
    }
    if language:
        body["language"] = language
    if prompt:
        body["prompt"] = prompt
    if response_format:
        body["response_format"] = response_format
    if temperature is not None:
        body["temperature"] = temperature

    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.AUDIO_TRANSCRIPTION)
    try:
        result = await use_case.audio_transcription(ctx, body)
    except Exception as exc:
        raise _wrap_business_errors(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/audio/speech
# =============================================================================


@router.post("/audio/speech")
async def audio_speech(
    body: dict[str, Any],
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.AUDIO_SPEECH)
    try:
        result = await use_case.audio_speech(ctx, body)
    except Exception as exc:
        raise _wrap_business_errors(exc) from exc
    if isinstance(result, bytes):
        return Response(content=result, media_type="audio/mpeg")
    if hasattr(result, "content"):
        return Response(
            content=result.content,
            media_type=str(getattr(result, "content_type", "audio/mpeg")),
        )
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/rerank
# =============================================================================


@router.post("/rerank")
async def rerank(
    body: dict[str, Any],
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.RERANK)
    try:
        result = await use_case.rerank(ctx, body)
    except Exception as exc:
        raise _wrap_business_errors(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/models
# =============================================================================


@router.get("/models")
async def list_models(
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    reads = GatewayManagementReadService(db)
    models = await reads.list_gateway_models(principal.team_id, only_enabled=True)
    if principal.vkey and principal.vkey.allowed_models:
        allowed = set(principal.vkey.allowed_models)
        models = [m for m in models if m.name in allowed]
    return {
        "object": "list",
        "data": [
            {
                "id": m.name,
                "object": "model",
                "created": int(m.created_at.timestamp()),
                "owned_by": m.provider,
                "capability": m.capability,
            }
            for m in models
        ],
    }


__all__ = ["router"]
