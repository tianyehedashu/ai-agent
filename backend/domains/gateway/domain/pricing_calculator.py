"""定价纯函数：按 rate 与 token 用量计算 USD 金额。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domains.gateway.domain.money import MoneyUSD


@dataclass(frozen=True)
class PricingRate:
    """与 LiteLLM / ORM 对齐的单价快照。"""

    input_cost_per_token: Decimal
    output_cost_per_token: Decimal
    cache_creation_input_token_cost: Decimal | None = None
    cache_read_input_token_cost: Decimal | None = None
    per_request_usd: Decimal | None = None
    version: int = 1
    source: str = "manual"
    inheritance_strategy: str | None = None


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    requests: int = 1


@dataclass(frozen=True)
class CostBreakdown:
    upstream_cost: MoneyUSD
    downstream_revenue: MoneyUSD
    margin: MoneyUSD
    rate_snapshot: dict[str, object]


def calculate_cost_from_rate(
    rate: PricingRate,
    usage: TokenUsage,
    *,
    zero_amount: bool = False,
) -> MoneyUSD:
    """按单价 × token 计算总额；``zero_amount=True`` 时用于套餐内调用。"""
    if zero_amount:
        return MoneyUSD(amount=Decimal("0"))
    total = Decimal("0")
    total += rate.input_cost_per_token * Decimal(usage.input_tokens)
    total += rate.output_cost_per_token * Decimal(usage.output_tokens)
    if rate.cache_creation_input_token_cost is not None:
        total += rate.cache_creation_input_token_cost * Decimal(usage.cache_creation_tokens)
    if rate.cache_read_input_token_cost is not None:
        total += rate.cache_read_input_token_cost * Decimal(usage.cache_read_tokens)
    if rate.per_request_usd is not None:
        total += rate.per_request_usd * Decimal(usage.requests)
    return MoneyUSD(amount=total)


def build_breakdown(
    *,
    upstream_cost: MoneyUSD,
    downstream_revenue: MoneyUSD,
    rate_snapshot: dict[str, object],
) -> CostBreakdown:
    margin = MoneyUSD(amount=downstream_revenue.amount - upstream_cost.amount)
    return CostBreakdown(
        upstream_cost=upstream_cost,
        downstream_revenue=downstream_revenue,
        margin=margin,
        rate_snapshot=rate_snapshot,
    )


__all__ = [
    "CostBreakdown",
    "PricingRate",
    "TokenUsage",
    "build_breakdown",
    "calculate_cost_from_rate",
]
