"""Chat / Anthropic Messages 代理入站公共流水线（校验、预算、kwargs 准备）。

依赖 ``ProxyUseCase`` 的「Application 内部协作 API」（``_check_*`` / ``_release_*``
等 ``_``-前缀方法）。该耦合在 ``ProxyUseCase`` 类 docstring 中已显式登记；本模块仅
被 ``ProxyUseCase`` 的公开入口（``chat_completion`` / ``anthropic_messages``）调用，
不暴露给 presentation 或其它域。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domains.gateway.application.pricing.pricing_proxy_metadata import (
    downstream_custom_from_metadata,
    upstream_custom_from_metadata,
)
from domains.gateway.domain.errors import EntitlementPlanExhaustedError
from domains.gateway.domain.types import GatewayCapability

if TYPE_CHECKING:
    from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase

BudgetReservation = tuple[str, str | None, str, str | None]
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

    use_case._check_model(model, ctx)
    use_case._check_capability(ctx)
    await use_case._assert_request_capability_matches_model(ctx, model)
    await use_case._check_limits(ctx, estimate_tokens=estimate_tokens)
    reservations = await use_case._check_budget(ctx)
    try:
        await use_case._check_entitlement(ctx, model, estimate_tokens=estimate_tokens)
    except EntitlementPlanExhaustedError:
        await use_case._release_budget_reservations(reservations)
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


async def invoke_litellm_with_direct_fallback(
    use_case: ProxyUseCase,
    ctx: ProxyContext,
    model: str,
    reservations: list[BudgetReservation],
    *,
    use_direct: bool,
    direct_call: Callable[[], Awaitable[Any]],
    router_call: Callable[[], Awaitable[Any]],
) -> Any:
    """Router 调用；model miss 时回退直连，失败时释放预扣。"""
    try:
        if use_direct:
            return await direct_call()
        return await router_call()
    except Exception as exc:
        if use_case._is_router_model_miss(
            exc
        ) and await use_case._should_use_internal_direct_litellm(ctx, model):
            try:
                return await direct_call()
            except Exception:
                await use_case._release_budget_reservations(reservations)
                await use_case._release_entitlement_reservations(ctx)
                raise
        await use_case._release_budget_reservations(reservations)
        await use_case._release_entitlement_reservations(ctx)
        raise


__all__ = [
    "ChatProxyPrepared",
    "apply_stream_cost_defer_flag",
    "invoke_litellm_with_direct_fallback",
    "prepare_chat_proxy_request",
]
