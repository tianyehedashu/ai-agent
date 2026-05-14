"""OpenAI / Anthropic 对外代理路由共享：从鉴权主体构造 ``ProxyContext``。"""

from __future__ import annotations

import uuid

from domains.gateway.application.proxy_use_case import ProxyContext
from domains.gateway.domain.types import GatewayCapability, GatewayInboundVia
from domains.gateway.presentation.deps import VkeyOrApikeyPrincipal


def proxy_context_from_gateway_principal(
    principal: VkeyOrApikeyPrincipal,
    capability: GatewayCapability,
) -> ProxyContext:
    """单次对外代理调用的 ``ProxyContext``（虚拟 Key 与业务 API Key 共用）。"""
    vkey = principal.vkey
    inbound_via: GatewayInboundVia = principal.via
    return ProxyContext(
        team_id=principal.team_id,
        user_id=principal.user_id,
        vkey=vkey,
        inbound_via=inbound_via,
        platform_api_key_id=principal.platform_api_key_id,
        capability=capability,
        request_id=str(uuid.uuid4()),
        store_full_messages=vkey.store_full_messages if vkey else False,
        guardrail_enabled=vkey.guardrail_enabled if vkey else True,
    )


__all__ = ["proxy_context_from_gateway_principal"]
