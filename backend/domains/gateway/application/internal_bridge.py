"""
Internal Bridge - GatewayProxyProtocol 的实现

供 agent/session 等内部域使用：把 LLM 调用通过 Gateway 走，
享受统一统计、限流、预算、Guardrail、Fallback。

策略：
- 自动取/创建用户 personal team
- 用 system vkey 走 Gateway（不计算外部 sk-gw 限额）
- 仍然写完整日志与统计
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.ports import (
    GatewayCallContext,
    GatewayResponse,
    GatewayStreamChunk,
)
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.types import (
    GatewayCapability,
    VirtualKeyPrincipal,
    allowed_capabilities_from_storage,
)
from domains.gateway.domain.virtual_key_service import generate_vkey
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.db.database import get_session_context
from utils.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession


def _merge_gateway_ctx_metadata(body: dict[str, Any], ctx: GatewayCallContext) -> None:
    """将 ``GatewayCallContext.metadata`` 并入请求体 ``metadata``（不覆盖已有键）。"""
    extra = ctx.metadata
    if not extra:
        return
    base: dict[str, Any] = dict(body["metadata"]) if isinstance(body.get("metadata"), dict) else {}
    for key, val in extra.items():
        if key not in base:
            base[key] = val
    body["metadata"] = base


def _encryption_key() -> str:
    return derive_encryption_key(settings.secret_key.get_secret_value())


@asynccontextmanager
async def _session_scope() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_context() as session:
        yield session


async def _ensure_system_vkey(
    session: AsyncSession,
    team_id: uuid.UUID,
) -> VirtualKeyPrincipal:
    """获取/创建该团队的 system vkey"""
    repo = VirtualKeyRepository(session)
    plain, key_id_str, key_hash = generate_vkey()
    encrypted = encrypt_value(plain, _encryption_key())
    record = await repo.get_or_create_system_key(
        team_id,
        encrypted_key=encrypted,
        key_hash=key_hash,
        key_id_str=key_id_str,
    )
    try:
        caps = allowed_capabilities_from_storage(record.allowed_capabilities)
    except ValueError as exc:
        logger.exception(
            "system virtual key %s has invalid allowed_capabilities",
            record.id,
        )
        raise RuntimeError(
            "Invalid system virtual key capability configuration",
        ) from exc

    return VirtualKeyPrincipal(
        vkey_id=record.id,
        vkey_name=record.name,
        team_id=record.team_id,
        user_id=record.created_by_user_id,
        allowed_models=tuple(record.allowed_models or ()),
        allowed_capabilities=caps,
        rpm_limit=record.rpm_limit,
        tpm_limit=record.tpm_limit,
        store_full_messages=record.store_full_messages,
        guardrail_enabled=record.guardrail_enabled,
        is_system=True,
    )


def _to_gateway_response(data: dict[str, Any]) -> GatewayResponse:
    choices = data.get("choices") or []
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message", {}) or {}
        content = msg.get("content")
        reasoning_content = msg.get("reasoning_content")
        tool_calls = msg.get("tool_calls")
        finish_reason = choices[0].get("finish_reason")
    usage = data.get("usage") or None
    return GatewayResponse(
        content=content,
        reasoning_content=reasoning_content,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        usage=usage if isinstance(usage, dict) else None,
        cost_usd=Decimal(str(data.get("cost_usd"))) if data.get("cost_usd") else None,
        model=data.get("model"),
        cache_hit=bool(data.get("cache_hit")),
        raw=data,
    )


class GatewayBridge:
    """``GatewayProxyProtocol`` 的具体实现（见 ``application.ports``）。"""

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        ctx: GatewayCallContext,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> GatewayResponse | AsyncGenerator[GatewayStreamChunk, None]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
        if response_format:
            body["response_format"] = response_format
        body.update(kwargs)
        if api_key is not None:
            body["api_key"] = api_key
        if api_base is not None:
            body["api_base"] = api_base

        _merge_gateway_ctx_metadata(body, ctx)

        async with _session_scope() as session:
            team_id = ctx.team_id
            if team_id is None:
                team = await TeamService(session).ensure_personal_team(ctx.user_id)
                team_id = team.id
            vkey = await _ensure_system_vkey(session, team_id)
            proxy_ctx = ProxyContext(
                team_id=team_id,
                user_id=ctx.user_id,
                vkey=vkey,
                inbound_via="vkey",
                platform_api_key_id=None,
                capability=GatewayCapability.CHAT,
                request_id=ctx.request_id or str(uuid.uuid4()),
                store_full_messages=(
                    ctx.store_full_messages
                    if ctx.store_full_messages is not None
                    else vkey.store_full_messages
                ),
                guardrail_enabled=vkey.guardrail_enabled,
            )
            result = await ProxyUseCase(session).chat_completion(proxy_ctx, body)

        if stream:

            async def _wrap() -> AsyncGenerator[GatewayStreamChunk, None]:
                async for chunk in result:  # type: ignore[union-attr]
                    choices = chunk.get("choices") or []
                    delta = (
                        choices[0].get("delta", {})
                        if choices and isinstance(choices[0], dict)
                        else {}
                    )
                    yield GatewayStreamChunk(
                        content=delta.get("content"),
                        reasoning_content=delta.get("reasoning_content"),
                        tool_calls=delta.get("tool_calls"),
                        finish_reason=(
                            choices[0].get("finish_reason")
                            if choices and isinstance(choices[0], dict)
                            else None
                        ),
                        usage=chunk.get("usage"),
                    )

            return _wrap()
        return _to_gateway_response(result if isinstance(result, dict) else {})

    async def embedding(
        self,
        inputs: str | list[str],
        *,
        ctx: GatewayCallContext,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        body: dict[str, Any] = {
            "model": model,
            "input": inputs,
        }
        body.update(kwargs)
        if api_key is not None:
            body["api_key"] = api_key
        if api_base is not None:
            body["api_base"] = api_base

        _merge_gateway_ctx_metadata(body, ctx)

        async with _session_scope() as session:
            team_id = ctx.team_id
            if team_id is None:
                team = await TeamService(session).ensure_personal_team(ctx.user_id)
                team_id = team.id
            vkey = await _ensure_system_vkey(session, team_id)
            proxy_ctx = ProxyContext(
                team_id=team_id,
                user_id=ctx.user_id,
                vkey=vkey,
                inbound_via="vkey",
                platform_api_key_id=None,
                capability=GatewayCapability.EMBEDDING,
                request_id=ctx.request_id or str(uuid.uuid4()),
                store_full_messages=False,
                guardrail_enabled=vkey.guardrail_enabled,
            )
            result = await ProxyUseCase(session).embedding(proxy_ctx, body)
        if isinstance(result, dict):
            data = result.get("data") or []
            return [item.get("embedding") for item in data if isinstance(item, dict)]
        return []

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        try:
            from litellm import token_counter

            return int(token_counter(model=model or "gpt-4", text=text))
        except Exception:
            import tiktoken

            try:
                enc = tiktoken.encoding_for_model(model or "gpt-4")
            except KeyError:
                enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))


_bridge_singleton: GatewayBridge | None = None


def get_gateway_bridge() -> GatewayBridge:
    """获取桥接单例"""
    global _bridge_singleton  # pylint: disable=global-statement
    if _bridge_singleton is None:
        _bridge_singleton = GatewayBridge()
    return _bridge_singleton


__all__ = ["GatewayBridge", "get_gateway_bridge"]
