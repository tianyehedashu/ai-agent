"""代理回调侧费用结算（上游成本 vs 下游收入）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from domains.gateway.domain.pricing_calculator import (
    PricingRate,
    TokenUsage,
    calculate_cost_from_rate,
)

_BILLING_PACKAGE_ENTITLEMENT = "entitlement"
_BILLING_PACKAGE_PROVIDER = "provider"


def pricing_rate_from_metadata(custom: dict[str, Any]) -> PricingRate | None:
    inp = custom.get("input_cost_per_token")
    out = custom.get("output_cost_per_token")
    if inp is None or out is None:
        return None
    return PricingRate(
        input_cost_per_token=Decimal(str(inp)),
        output_cost_per_token=Decimal(str(out)),
        cache_creation_input_token_cost=(
            Decimal(str(custom["cache_creation_input_token_cost"]))
            if custom.get("cache_creation_input_token_cost") is not None
            else None
        ),
        cache_read_input_token_cost=(
            Decimal(str(custom["cache_read_input_token_cost"]))
            if custom.get("cache_read_input_token_cost") is not None
            else None
        ),
    )


def settle_request_log_amounts(
    *,
    metadata: dict[str, Any],
    litellm_cost_usd: Decimal,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
) -> tuple[Decimal, Decimal, dict[str, Any]]:
    """返回 (cost_usd 上游, revenue_usd 下游, pricing_snapshot 扩展字段)。"""
    package = metadata.get("gateway_billing_package")
    if package in (_BILLING_PACKAGE_ENTITLEMENT, _BILLING_PACKAGE_PROVIDER):
        zero = Decimal("0")
        extra: dict[str, Any] = {
            "billing_package": package,
            "metering_mode": "package",
            "hit_chain": metadata.get("gateway_pricing_hit_chain"),
        }
        if litellm_cost_usd > 0:
            extra["shadow_upstream_cost_usd"] = float(litellm_cost_usd)
        return zero, zero, extra

    usage = TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cached_tokens,
    )
    cost_usd = litellm_cost_usd

    downstream_custom = metadata.get("gateway_pricing_downstream")
    rate: PricingRate | None = None
    if isinstance(downstream_custom, dict):
        rate = pricing_rate_from_metadata(downstream_custom)

    revenue_usd = (
        cost_usd if rate is None else calculate_cost_from_rate(rate, usage).amount
    )

    extra: dict[str, Any] = {
        "hit_chain": metadata.get("gateway_pricing_hit_chain"),
        "gateway_model_id": metadata.get("gateway_gateway_model_id"),
        "metering_mode": "payg",
    }
    if rate is not None:
        extra["downstream_input_cost_per_token"] = str(rate.input_cost_per_token)
        extra["downstream_output_cost_per_token"] = str(rate.output_cost_per_token)
    return cost_usd, revenue_usd, extra


def merge_pricing_snapshot(
    base: dict[str, Any],
    settlement_extra: dict[str, Any],
    *,
    cost_usd: Decimal,
    revenue_usd: Decimal,
) -> dict[str, Any]:
    merged = dict(base)
    merged["upstream_cost_usd"] = float(cost_usd)
    merged["downstream_revenue_usd"] = float(revenue_usd)
    merged.update({k: v for k, v in settlement_extra.items() if v is not None})
    return merged


__all__ = [
    "merge_pricing_snapshot",
    "pricing_rate_from_metadata",
    "settle_request_log_amounts",
]
