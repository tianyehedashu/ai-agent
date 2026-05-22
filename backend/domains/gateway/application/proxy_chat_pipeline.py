"""Chat / Anthropic Messages 代理入站公共流水线（校验、预算、kwargs 准备）。

校验/限流/预算/entitlement 经 :class:`ProxyGuard` 公开 API 完成（``check_*`` /
``release_*``），不再访问 ``ProxyUseCase`` 的 ``_``-前缀方法；下游 LiteLLM 调度
（kwargs 准备、router miss 判定、直连降级判定）仍由 ``ProxyUseCase`` 内部 helper
负责，本模块仅做编排穿透。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domains.gateway.application.pricing.pricing_proxy_metadata import (
    downstream_custom_from_metadata,
    upstream_custom_from_metadata,
)
from domains.gateway.application.proxy_router_invoke import invoke_router_with_direct_fallback
from domains.gateway.domain.errors import EntitlementPlanExhaustedError
from domains.gateway.domain.types import GatewayCapability

if TYPE_CHECKING:
    from domains.gateway.application.proxy_guard import BudgetReservation
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

    ctx.capability = GatewayCapability.CHAT
    model = str(body.get("model", "")).strip()
    if require_model and not model:
        raise ValueError("model is required")
    ctx.budget_model = model

    guard = use_case.guard
    guard.check_model(model, ctx)
    guard.check_capability(ctx)
    await guard.assert_request_capability_matches_model(ctx, model)
    await guard.check_limits(ctx, estimate_tokens=estimate_tokens)
    reservations = await guard.check_budget(ctx)
    try:
        await guard.check_entitlement(ctx, model, estimate_tokens=estimate_tokens)
    except EntitlementPlanExhaustedError:
        await guard.release_budget_reservations(reservations)
        raise

    kwargs = await use_case._prepare_litellm_kwargs(ctx, body)
    meta = kwargs.get("metadata")
    metadata: dict[str, Any] = meta if isinstance(meta, dict) else {}
    stream = bool(body.get("stream"))
    apply_stream_cost_defer_flag(metadata, stream=stream)

    return ChatProxyPrepared(
        model=model,
        reservations=reservations,
        kwargs=kwargs,
        metadata=metadata,
        downstream_custom=downstream_custom_from_metadata(metadata),
        upstream_custom=upstream_custom_from_metadata(metadata),
        stream=stream,
    )


__all__ = [
    "ChatProxyPrepared",
    "apply_stream_cost_defer_flag",
    "invoke_router_with_direct_fallback",
    "prepare_chat_proxy_request",
]
