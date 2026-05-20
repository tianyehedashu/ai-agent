"""
OpenAI 兼容入口（挂载在根路径 /）

提供：
- POST /v1/chat/completions（含 SSE）
- POST /v1/embeddings
- POST /v1/images/generations
- POST /v1/videos
- POST /v1/moderations
- POST /v1/audio/transcriptions
- POST /v1/audio/speech
- POST /v1/rerank
- GET  /v1/models
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
import orjson
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.entitlement_model_status import resolve_entitlement_scope
from domains.gateway.application.management import GatewayManagementReadService
from domains.gateway.application.proxy_model_list_reads import build_proxy_models_list
from domains.gateway.application.proxy_use_case import ProxyUseCase
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.presentation.deps import (
    VkeyOrApikeyPrincipal,
    bearer_vkey_or_apikey_auth,
)
from domains.gateway.presentation.gateway_proxy_context import (
    proxy_context_from_gateway_principal,
)
from domains.gateway.presentation.proxy_request_context import (
    prepare_proxy_body,
    proxy_context_from_request,
    rate_limit_headers_for_context,
)
from domains.gateway.presentation.openai_compat_error_map import (
    openai_http_exception_from_proxy_business_error,
)
from libs.db.database import get_db
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", tags=["OpenAI Compat"])

OpenAiRequestBody = dict[str, object]


def _as_proxy_body(body: OpenAiRequestBody) -> dict[str, Any]:
    """``ProxyUseCase`` 仍使用 ``dict[str, Any]`` 承载 LiteLLM/OpenAI 动态字段。"""
    return cast("dict[str, Any]", body)


# =============================================================================
# /v1/chat/completions
# =============================================================================


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    body: OpenAiRequestBody,
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_request(principal, GatewayCapability.CHAT, request)
    proxy_body = prepare_proxy_body(body, request)
    try:
        result = await use_case.chat_completion(ctx, proxy_body)
    except Exception as exc:
        logger.warning("chat_completions failed: %s", exc)
        raise openai_http_exception_from_proxy_business_error(exc) from exc

    rate_headers = await rate_limit_headers_for_context(ctx, flavor="openai", use_case=use_case)

    if proxy_body.get("stream"):
        stream = cast("AsyncIterator[dict[str, Any]]", result)

        async def _sse() -> AsyncIterator[bytes]:
            async for chunk in stream:
                yield b"data: " + orjson.dumps(chunk) + b"\n\n"
            yield b"data: [DONE]\n\n"

        return StreamingResponse(
            _sse(),
            media_type="text/event-stream",
            headers=rate_headers,
        )
    return Response(
        content=orjson.dumps(result),
        media_type="application/json",
        headers=rate_headers,
    )


# =============================================================================
# /v1/embeddings
# =============================================================================


@router.post("/embeddings")
async def embeddings(
    body: OpenAiRequestBody,
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.EMBEDDING)
    try:
        result = await use_case.embedding(ctx, _as_proxy_body(body))
    except Exception as exc:
        raise openai_http_exception_from_proxy_business_error(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/images/generations
# =============================================================================


@router.post("/images/generations")
async def image_generations(
    body: OpenAiRequestBody,
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.IMAGE)
    try:
        result = await use_case.image_generation(ctx, _as_proxy_body(body))
    except Exception as exc:
        raise openai_http_exception_from_proxy_business_error(exc) from exc
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
    body: OpenAiRequestBody = {
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
        result = await use_case.audio_transcription(ctx, _as_proxy_body(body))
    except Exception as exc:
        raise openai_http_exception_from_proxy_business_error(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/audio/speech
# =============================================================================


@router.post("/audio/speech")
async def audio_speech(
    body: OpenAiRequestBody,
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.AUDIO_SPEECH)
    try:
        result = await use_case.audio_speech(ctx, _as_proxy_body(body))
    except Exception as exc:
        raise openai_http_exception_from_proxy_business_error(exc) from exc
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
    body: OpenAiRequestBody,
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.RERANK)
    try:
        result = await use_case.rerank(ctx, _as_proxy_body(body))
    except Exception as exc:
        raise openai_http_exception_from_proxy_business_error(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/moderations
# =============================================================================


@router.post("/moderations")
async def moderations(
    body: OpenAiRequestBody,
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.MODERATION)
    try:
        result = await use_case.moderation(ctx, _as_proxy_body(body))
    except Exception as exc:
        raise openai_http_exception_from_proxy_business_error(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/videos
# =============================================================================


@router.post("/videos")
async def videos(
    body: OpenAiRequestBody,
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    use_case = ProxyUseCase(db)
    ctx = proxy_context_from_gateway_principal(principal, GatewayCapability.VIDEO_GENERATION)
    try:
        result = await use_case.video_generation(ctx, _as_proxy_body(body))
    except Exception as exc:
        raise openai_http_exception_from_proxy_business_error(exc) from exc
    return Response(content=orjson.dumps(result), media_type="application/json")


# =============================================================================
# /v1/models
# =============================================================================


@router.get("/models")
async def list_models(
    principal: Annotated[VkeyOrApikeyPrincipal, Depends(bearer_vkey_or_apikey_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    reads = GatewayManagementReadService(db)
    models = await reads.list_gateway_models(principal.team_id, only_enabled=True)
    if principal.vkey and principal.vkey.allowed_models:
        allowed = set(principal.vkey.allowed_models)
        models = [m for m in models if m.name in allowed]
    if principal.api_key_grant and principal.api_key_grant.allowed_models:
        allowed = set(principal.api_key_grant.allowed_models)
        models = [m for m in models if m.name in allowed]
    entitlement_scope, entitlement_scope_id = resolve_entitlement_scope(
        vkey_id=principal.vkey.vkey_id if principal.vkey else None,
        apikey_grant_id=principal.api_key_grant.grant_id if principal.api_key_grant else None,
    )
    data = await build_proxy_models_list(
        db,
        models,
        entitlement_scope=entitlement_scope,
        entitlement_scope_id=entitlement_scope_id,
    )
    return {"object": "list", "data": data}


__all__ = ["router"]
