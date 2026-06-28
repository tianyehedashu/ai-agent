"""定价计算器单元测试。"""

from decimal import Decimal

import pytest

from domains.gateway.domain.pricing.pricing_calculator import (
    PricingRate,
    TokenUsage,
    calculate_cost_from_rate,
)


@pytest.mark.unit
def test_calculate_cost_from_rate_basic() -> None:
    rate = PricingRate(
        input_cost_per_token=Decimal("0.000001"),
        output_cost_per_token=Decimal("0.000002"),
    )
    usage = TokenUsage(input_tokens=1000, output_tokens=500)
    cost = calculate_cost_from_rate(rate, usage)
    assert cost.amount == Decimal("0.002")


@pytest.mark.unit
def test_calculate_cost_zero_when_plan() -> None:
    rate = PricingRate(
        input_cost_per_token=Decimal("1"),
        output_cost_per_token=Decimal("1"),
    )
    cost = calculate_cost_from_rate(rate, TokenUsage(input_tokens=999), zero_amount=True)
    assert cost.amount == Decimal("0")
