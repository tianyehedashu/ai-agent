"""OpenAI / Anthropic 对外代理路由共享：从鉴权主体构造 ``ProxyContext``。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.gateway.application.vkey.vkey_team_resolution import (
    assert_vkey_model_not_ambiguous,
    dispatch_vkey_model,
)
from domains.gateway.application.proxy.proxy_context import ProxyContext
from domains.gateway.domain.types import GatewayCapability, GatewayInboundVia
from domains.gateway.presentation.deps import VkeyOrApikeyPrincipal


async def apply_vkey_team_dispatch(
    ctx: ProxyContext,
    proxy_body: dict[str, object],
    session: AsyncSession,
) -> None:
    """对 vkey 入站调用应用跨团队派发（重写 model 与 ctx.team_id）。

    副作用（仅在 vkey + body 含 model 字段时生效）：
    - proxy_body["model"] 改为派发后的模型名
    - ctx.team_id 改为派发后的 effective_team_id
    - ctx.budget_model 同步更新
    - ctx.client_raw_model / ctx.dispatched_via_prefix 标记
    """
    if ctx.vkey is None:
        return
    raw_model = proxy_body.get("model")
    if not isinstance(raw_model, str) or not raw_model:
        return

    dispatch = await dispatch_vkey_model(
        session,
        vkey=ctx.vkey,
        raw_model=raw_model,
        strict=settings.gateway_vkey_strict_team_prefix,
    )

    await assert_vkey_model_not_ambiguous(
        session,
        vkey=ctx.vkey,
        dispatch=dispatch,
        strict=settings.gateway_vkey_strict_team_prefix,
    )

    ctx.client_raw_model = raw_model
    ctx.dispatched_via_prefix = dispatch.matched_slug is not None
    if dispatch.matched_slug is not None:
        ctx.team_id = dispatch.effective_team_id
        ctx.budget_model = dispatch.real_model_name
        proxy_body["model"] = dispatch.real_model_name


def proxy_context_from_gateway_principal(
    principal: VkeyOrApikeyPrincipal,
    capability: GatewayCapability,
    *,
    client_ua: str | None = None,
    client_type: str = "unknown",
) -> ProxyContext:
    """单次对外代理调用的 ``ProxyContext``（虚拟 Key 与业务 API Key 共用）。"""
    vkey = principal.vkey
    grant = principal.api_key_grant
    inbound_via: GatewayInboundVia = principal.via
    return ProxyContext(
        team_id=principal.team_id,
        user_id=principal.user_id,
        vkey=vkey,
        inbound_via=inbound_via,
        platform_api_key_id=principal.platform_api_key_id,
        platform_api_key_grant_id=grant.grant_id if grant else None,
        capability=capability,
        request_id=str(uuid.uuid4()),
        store_full_messages=(
            vkey.store_full_messages if vkey else grant.store_full_messages if grant else False
        ),
        guardrail_enabled=(
            vkey.guardrail_enabled if vkey else grant.guardrail_enabled if grant else False
        ),
        allowed_models=(vkey.allowed_models if vkey else grant.allowed_models if grant else ()),
        allowed_capabilities=(
            vkey.allowed_capabilities if vkey else grant.allowed_capabilities if grant else ()
        ),
        rpm_limit=vkey.rpm_limit if vkey else grant.rpm_limit if grant else None,
        tpm_limit=vkey.tpm_limit if vkey else grant.tpm_limit if grant else None,
        client_ua=client_ua,
        client_type=client_type,
        user_display_snapshot=principal.user_display_snapshot,
    )


__all__ = ["apply_vkey_team_dispatch", "proxy_context_from_gateway_principal"]
