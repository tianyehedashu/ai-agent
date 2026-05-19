"""custom_logger 与 pricing_settlement 联动。"""

from decimal import Decimal

from domains.gateway.infrastructure.callbacks.custom_logger import (
    _build_pricing_snapshot,
    _extract_gateway_metadata,
)
from domains.gateway.application.pricing.pricing_settlement import (
    merge_pricing_snapshot,
    settle_request_log_amounts,
)


def test_settle_splits_upstream_and_downstream() -> None:
    metadata = {
        "gateway_pricing_downstream": {
            "input_cost_per_token": 0.000002,
            "output_cost_per_token": 0.000004,
        }
    }
    cost, revenue, _ = settle_request_log_amounts(
        metadata=metadata,
        litellm_cost_usd=Decimal("0.001"),
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=0,
    )
    assert cost == Decimal("0.001")
    assert revenue == Decimal("0.004")


def test_merge_pricing_snapshot_includes_revenue() -> None:
    metadata = {
        "gateway_pricing_downstream": {
            "input_cost_per_token": 0.000002,
            "output_cost_per_token": 0.000004,
        }
    }
    cost, revenue, extra = settle_request_log_amounts(
        metadata=metadata,
        litellm_cost_usd=Decimal("0.01"),
        input_tokens=100,
        output_tokens=50,
        cached_tokens=0,
    )
    snap = merge_pricing_snapshot(
        _build_pricing_snapshot({}, None, cost),
        extra,
        cost_usd=cost,
        revenue_usd=revenue,
    )
    assert snap["upstream_cost_usd"] == 0.01
    assert snap["downstream_revenue_usd"] == float(revenue)


def test_extract_metadata_merges_litellm_params() -> None:
    kwargs = {
        "metadata": {"gateway_team_id": "00000000-0000-4000-8000-000000000001"},
        "litellm_params": {
            "metadata": {
                "gateway_pricing_downstream": {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6}
            }
        },
    }
    meta = _extract_gateway_metadata(kwargs)
    assert "gateway_team_id" in meta
    assert "gateway_pricing_downstream" in meta
