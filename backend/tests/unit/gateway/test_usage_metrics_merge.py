"""``merge_gateway_usage_slices`` 纯函数单测。"""

from decimal import Decimal

from domains.gateway.application.management.usage_metrics import merge_gateway_usage_slices


def test_merge_gateway_usage_slices_adds_counts_and_decimal_cost() -> None:
    a = {
        "requests": 1,
        "input_tokens": 10,
        "output_tokens": 20,
        "cost_usd": Decimal("0.1"),
    }
    b = {
        "requests": 2,
        "input_tokens": 5,
        "output_tokens": 7,
        "cost_usd": "0.2",
    }
    out = merge_gateway_usage_slices(a, b)
    assert out["requests"] == 3
    assert out["input_tokens"] == 15
    assert out["output_tokens"] == 27
    assert out["cost_usd"] == Decimal("0.3")


def test_merge_gateway_usage_slices_handles_missing_keys() -> None:
    out = merge_gateway_usage_slices({}, {"requests": 1, "cost_usd": 0})
    assert out["requests"] == 1
    assert out["input_tokens"] == 0
    assert out["output_tokens"] == 0
    assert out["cost_usd"] == Decimal("0")
