"""pricing_settlement 单元测试。"""

from decimal import Decimal

from domains.gateway.application.pricing.pricing_settlement import settle_request_log_amounts


def test_entitlement_package_zeros_both_amounts() -> None:
    cost, revenue, extra = settle_request_log_amounts(
        metadata={"gateway_billing_package": "entitlement"},
        litellm_cost_usd=Decimal("0.01"),
        input_tokens=100,
        output_tokens=50,
        cached_tokens=0,
    )
    assert cost == Decimal("0")
    assert revenue == Decimal("0")
    assert extra.get("billing_package") == "entitlement"
    assert extra.get("metering_mode") == "package"
    assert extra.get("shadow_upstream_cost_usd") == 0.01


def test_downstream_rate_computes_revenue() -> None:
    cost, revenue, _ = settle_request_log_amounts(
        metadata={
            "gateway_pricing_downstream": {
                "input_cost_per_token": 0.000002,
                "output_cost_per_token": 0.000004,
            }
        },
        litellm_cost_usd=Decimal("0.001"),
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=0,
    )
    assert cost == Decimal("0.001")
    assert revenue == Decimal("0.004")
