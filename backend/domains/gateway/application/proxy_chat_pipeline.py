"""Chat / Anthropic Messages 代理入站公共流水线（校验、预算、kwargs 准备）。

校验/限流/预算/entitlement 经 :func:`run_proxy_inbound_preflight` 完成；
LiteLLM kwargs 经 ``ProxyUseCase.prepare_litellm_kwargs`` 拼装。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domains.gateway.application.pricing.pricing_proxy_metadata import (
    downstream_custom_from_metadata,
    upstream_custom_from_metadata,
)
from domains.gateway.application.proxy_inbound_preflight import run_proxy_inbound_preflight
from domains.gateway.application.proxy_vision_image_urls import inline_vision_image_urls_in_kwargs
from domains.gateway.domain.proxy_policy import BudgetReservation
from domains.gateway.domain.types import GatewayCapability

if TYPE_CHECKING:
    from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase

BodyValidator = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ChatProxyPrepared:
    """``chat_completion`` / ``anthropic_messages`` 共用准备结果。"""

    model: str
    reservations: list[BudgetReservation]
    kwargs: dict[str, Any]
    metadata: dict[str, Any]
    downstream_custom: dict[str, float] | None
    upstream_custom: dict[str, float] | None
    stream: bool


def apply_stream_cost_defer_flag(metadata: dict[str, Any] | None, *, stream: bool) -> None:
    """流式请求标记成本由 callback / 流结束兜底结算，避免 proxy 与 callback 双计。"""
    if stream and isinstance(metadata, dict):
        metadata["gateway_defer_cost_settlement"] = True


async def prepare_chat_proxy_request(
    use_case: ProxyUseCase,
    ctx: ProxyContext,
    body: dict[str, Any],
    *,
    estimate_tokens: int,
    require_model: bool = True,
    body_validator: BodyValidator | None = None,
) -> ChatProxyPrepared:
    """校验、限流、预算预扣、拼装 LiteLLM kwargs（与具体出站 API 无关）。"""
    if body_validator is not None:
        body_validator(body)

    model = str(body.get("model", "")).strip()
    preflight = await run_proxy_inbound_preflight(
        use_case.guard,
        ctx,
        capability=GatewayCapability.CHAT,
        model=model,
        require_model=require_model,
        estimate_tokens=estimate_tokens,
    )
    assert preflight.model is not None

    kwargs = await use_case.prepare_litellm_kwargs(ctx, body)
    kwargs = await inline_vision_image_urls_in_kwargs(use_case.session, kwargs)
    meta = kwargs.get("metadata")
    metadata: dict[str, Any] = meta if isinstance(meta, dict) else {}
    stream = bool(body.get("stream"))
    apply_stream_cost_defer_flag(metadata, stream=stream)

    return ChatProxyPrepared(
        model=preflight.model,
        reservations=preflight.reservations,
        kwargs=kwargs,
        metadata=metadata,
        downstream_custom=downstream_custom_from_metadata(metadata),
        upstream_custom=upstream_custom_from_metadata(metadata),
        stream=stream,
    )


__all__ = [
    "ChatProxyPrepared",
    "apply_stream_cost_defer_flag",
    "prepare_chat_proxy_request",
]
