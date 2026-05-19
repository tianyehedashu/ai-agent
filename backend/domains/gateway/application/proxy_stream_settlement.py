"""流式代理结束时的 token / 成本结算（与 callback 幂等协作）。"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from domains.gateway.application.anthropic_native_adapt import anthropic_usage_total_tokens
from domains.gateway.application.pricing.pricing_budget_cost import proxy_budget_cost_usd
from domains.gateway.application.pricing.upstream_cost_resolver import resolve_upstream_cost_usd

if TYPE_CHECKING:
    from domains.gateway.application.budget_service import BudgetService
    from domains.gateway.application.entitlement_guard import EntitlementGuard
    from domains.gateway.application.proxy_use_case import ProxyContext


def stream_usage_token_total(usage: dict[str, Any]) -> int:
    """从 OpenAI 或 Anthropic 形 usage 字典统计 token 总量。"""
    if "total_tokens" in usage:
        return int(usage.get("total_tokens", 0) or 0)
    return anthropic_usage_total_tokens(usage)


def resolve_stream_budget_cost_usd(
    usage: dict[str, Any],
    *,
    metadata: dict[str, Any],
    model: str | None,
    response_for_cost: Any | None = None,
) -> Decimal:
    """基于流末 usage 估算预算成本（与 callback 使用同一 resolver）。

    优先走 ``metadata['gateway_pricing_upstream']`` 的虚拟 Key 自定义 rate；命中即返回
    准确金额。未命中 rate 时会尝试 ``litellm.completion_cost`` 推断，对未注册到
    LiteLLM model_map 的虚拟模型可能返回 ``Decimal('0')``，此时由 LiteLLM callback
    （``commit_budget_from_callback``）落库 cost 后**幂等兜底**，避免漏计。
    """
    resp = response_for_cost if response_for_cost is not None else {"usage": usage}
    upstream, _source = resolve_upstream_cost_usd(
        response=resp,
        metadata=metadata,
        model=model,
    )
    _ = _source
    return proxy_budget_cost_usd(metadata, upstream)


async def finalize_deferred_stream_settlement(
    ctx: ProxyContext,
    budget: BudgetService,
    metadata: dict[str, Any],
    usage: dict[str, Any] | None,
    entitlement_guard: EntitlementGuard | None,
    *,
    response_for_cost: Any | None = None,
) -> None:
    """流式结束：commit token；defer 时由本函数与 callback 幂等 commit 成本。

    ``gateway_defer_cost_settlement`` 为真时，proxy 路径 ``settle_usage`` 的 ``cost`` 为 0，
    若 usage 可解析出成本则主动调用 ``commit_budget_from_callback``（Redis NX 幂等），
    避免仅依赖 LiteLLM callback 导致 Anthropic 原生流等场景漏计。
    """
    from domains.gateway.application.budget_callback_settlement import (
        commit_budget_from_callback,
    )
    from domains.gateway.application.proxy_response_adapter import settle_usage

    tokens = 0
    cost = Decimal("0")
    if usage:
        tokens = stream_usage_token_total(usage)
        if tokens > 0 or any(
            usage.get(k) for k in ("input_tokens", "output_tokens", "prompt_tokens")
        ):
            cost = resolve_stream_budget_cost_usd(
                usage,
                metadata=metadata,
                model=ctx.budget_model,
                response_for_cost=response_for_cost,
            )

    defer = bool(metadata.get("gateway_defer_cost_settlement"))
    if defer and cost > 0 and ctx.request_id:
        await commit_budget_from_callback(
            metadata=metadata,
            request_id=ctx.request_id,
            cost_usd=cost,
            total_tokens=tokens,
            budget_model=ctx.budget_model,
        )

    await settle_usage(
        ctx,
        budget,
        tokens=tokens,
        cost=Decimal("0") if defer else cost,
        requests=1,
        entitlement_guard=entitlement_guard,
        request_id=ctx.request_id,
    )


__all__ = [
    "finalize_deferred_stream_settlement",
    "resolve_stream_budget_cost_usd",
    "stream_usage_token_total",
]
