"""usage_metrics 合并纯函数单元测试。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from domains.gateway.application.management.usage_metrics import (
    merge_statistics_items,
    merge_summary_slices,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogUsageAggregateRow,
)


@pytest.mark.unit
def test_merge_summary_slices_weighted_latency() -> None:
    merged = merge_summary_slices(
        {
            "total": 10,
            "success": 8,
            "failure": 2,
            "input_tokens": 100,
            "output_tokens": 50,
            "cached_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": Decimal("1.0"),
            "avg_latency_ms": 100.0,
            "avg_ttfb_ms": 40.0,
        },
        {
            "total": 5,
            "success": 5,
            "failure": 0,
            "input_tokens": 20,
            "output_tokens": 10,
            "cached_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": Decimal("0.5"),
            "avg_latency_ms": 200.0,
            "avg_ttfb_ms": 60.0,
        },
    )
    assert merged["total"] == 15
    assert merged["success"] == 13
    assert merged["avg_latency_ms"] == pytest.approx((100 * 8 + 200 * 5) / 13)


@pytest.mark.unit
def test_merge_statistics_items_by_group_key() -> None:
    row_a = RequestLogUsageAggregateRow(
        group_key="model-a",
        label_snapshot=None,
        requests=3,
        success_count=2,
        failure_count=1,
        cost_usd=Decimal("1"),
    )
    row_b = RequestLogUsageAggregateRow(
        group_key="model-a",
        label_snapshot=None,
        requests=2,
        success_count=2,
        failure_count=0,
        cost_usd=Decimal("0.5"),
    )
    merged = merge_statistics_items([row_a], [row_b])
    assert len(merged) == 1
    assert merged[0].requests == 5
    assert merged[0].cost_usd == Decimal("1.5")
