"""套餐/包量路径预算成本。"""

from decimal import Decimal

from domains.gateway.application.pricing.pricing_budget_cost import proxy_budget_cost_usd


def test_package_billing_zeros_budget_cost() -> None:
    assert proxy_budget_cost_usd(
        {"gateway_billing_package": "entitlement"},
        Decimal("0.05"),
    ) == Decimal("0")
    assert proxy_budget_cost_usd(
        {"gateway_billing_package": "provider"},
        Decimal("0.05"),
    ) == Decimal("0")


def test_payg_keeps_upstream() -> None:
    assert proxy_budget_cost_usd({}, Decimal("0.05")) == Decimal("0.05")
