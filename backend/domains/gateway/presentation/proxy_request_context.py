"""对外 ``/v1/*`` 路由：从 FastAPI Request 提取代理上下文扩展字段。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from domains.gateway.application.proxy_rate_limit_headers import build_proxy_rate_limit_headers
from domains.gateway.application.proxy_use_case import ProxyContext
from domains.gateway.domain.client_type import infer_client_type, truncate_client_ua
from domains.gateway.domain.types import GatewayCapability
from domains.gateway.presentation.deps import VkeyOrApikeyPrincipal
from domains.gateway.presentation.gateway_proxy_context import proxy_context_from_gateway_principal
from domains.gateway.presentation.proxy_header_passthrough import merge_extra_headers_from_request

if TYPE_CHECKING:
    from fastapi import Request


def apply_inbound_proxy_request_context(
    body: dict[str, object],
    request: Request,
) -> tuple[str | None, str]:
    """合并透传头；返回 ``(client_ua, client_type)``。"""
    headers = dict(request.headers.items())
    merge_extra_headers_from_request(body, headers)
    client_ua = truncate_client_ua(request.headers.get("user-agent"))
    return client_ua, infer_client_type(client_ua)


def proxy_context_from_request(
    principal: VkeyOrApikeyPrincipal,
    capability: GatewayCapability,
    request: Request,
) -> ProxyContext:
    client_ua, client_type = apply_inbound_proxy_request_context({}, request)
    return proxy_context_from_gateway_principal(
        principal,
        capability,
        client_ua=client_ua,
        client_type=client_type,
    )


def prepare_proxy_body(body: dict[str, object], request: Request) -> dict[str, Any]:
    proxy_body = cast("dict[str, Any]", dict(body))
    apply_inbound_proxy_request_context(proxy_body, request)
    return proxy_body


async def rate_limit_headers_for_context(
    ctx: ProxyContext,
    *,
    flavor: str,
) -> dict[str, str]:
    """对外路由调用入口；reader 走 application 模块内置默认（Redis 实现）。"""
    return await build_proxy_rate_limit_headers(ctx, flavor=flavor)


__all__ = [
    "apply_inbound_proxy_request_context",
    "prepare_proxy_body",
    "proxy_context_from_request",
    "rate_limit_headers_for_context",
]
