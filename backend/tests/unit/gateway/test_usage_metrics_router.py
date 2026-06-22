"""UsageMetricsRouter hybrid 路由单元测试。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.usage_metrics_router import UsageMetricsRouter
from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.domain.usage_read_model import (
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    BreakdownPairRow,
    RequestLogUsageAggregateRow,
    RequestLogUsageTotals,
)


def _empty_totals() -> RequestLogUsageTotals:
    return RequestLogUsageTotals(0, 0, 0, 0, 0, 0, 0, Decimal("0"), 0.0, 0.0, 0)


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_all_hot_delegates_logs_only() -> None:
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    start = datetime(2026, 6, 10, 13, 0, tzinfo=UTC)
    end = datetime(2026, 6, 10, 15, 0, tzinfo=UTC)
    expected = ([], _empty_totals(), 0)
    logs.aggregate_usage_statistics_by_axis = AsyncMock(return_value=expected)

    with (
        patch.object(settings, "gateway_metrics_hybrid_read_enabled", True),
        patch(
            "domains.gateway.application.management.usage_metrics_router.compute_hot_cutoff",
            return_value=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
        ),
    ):
        result = await router.aggregate_usage_statistics(
            axis,
            start,
            end,
            group_by=UsageStatisticsGroupBy.MODEL,
            filters=UsageStatisticsFilters(),
            page=1,
            page_size=20,
        )

    assert result == expected
    logs.aggregate_usage_statistics_by_axis.assert_awaited_once()
    hourly.aggregate_usage_statistics_by_axis.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_all_cold_delegates_hourly_only() -> None:
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 2, 0, 0, tzinfo=UTC)
    hot_cutoff = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    row = RequestLogUsageAggregateRow(
        group_key="gpt-4",
        label_snapshot=None,
        requests=5,
        success_count=5,
        failure_count=0,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.1"),
        avg_latency_ms=10.0,
        avg_ttfb_ms=1.0,
        cache_hit_count=0,
    )
    totals = RequestLogUsageTotals(5, 5, 0, 10, 20, 0, 0, Decimal("0.1"), 10.0, 1.0, 0)
    hourly.aggregate_usage_statistics_by_axis = AsyncMock(return_value=([row], totals, 1))

    with (
        patch.object(settings, "gateway_metrics_hybrid_read_enabled", True),
        patch(
            "domains.gateway.application.management.usage_metrics_router.compute_hot_cutoff",
            return_value=hot_cutoff,
        ),
    ):
        items, merged_totals, group_total = await router.aggregate_usage_statistics(
            axis,
            start,
            end,
            group_by=UsageStatisticsGroupBy.MODEL,
            filters=UsageStatisticsFilters(),
            page=1,
            page_size=20,
        )

    assert len(items) == 1
    assert merged_totals.requests == 5
    assert group_total == 1
    hourly.aggregate_usage_statistics_by_axis.assert_awaited_once()
    assert (
        hourly.aggregate_usage_statistics_by_axis.await_args.kwargs.get("fetch_all_groups")
        is not True
    )
    logs.aggregate_usage_statistics_by_axis.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_hybrid_merges_cold_and_hot() -> None:
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    hot_cutoff = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    start = hot_cutoff - timedelta(days=1)
    end = datetime(2026, 6, 10, 15, 0, tzinfo=UTC)
    cold_row = RequestLogUsageAggregateRow(
        group_key="model-a",
        label_snapshot=None,
        requests=3,
        success_count=3,
        failure_count=0,
        input_tokens=6,
        output_tokens=9,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.03"),
        avg_latency_ms=10.0,
        avg_ttfb_ms=1.0,
        cache_hit_count=0,
    )
    hot_row = RequestLogUsageAggregateRow(
        group_key="model-a",
        label_snapshot=None,
        requests=2,
        success_count=2,
        failure_count=0,
        input_tokens=4,
        output_tokens=6,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.02"),
        avg_latency_ms=20.0,
        avg_ttfb_ms=2.0,
        cache_hit_count=0,
    )
    cold_totals = RequestLogUsageTotals(3, 3, 0, 6, 9, 0, 0, Decimal("0.03"), 10.0, 1.0, 0)
    hot_totals = RequestLogUsageTotals(2, 2, 0, 4, 6, 0, 0, Decimal("0.02"), 20.0, 2.0, 0)
    hourly.aggregate_usage_statistics_by_axis = AsyncMock(
        side_effect=[
            ([], cold_totals, 1),
            ([cold_row], cold_totals, 1),
        ]
    )
    logs.aggregate_usage_statistics_by_axis = AsyncMock(
        side_effect=[
            ([], hot_totals, 1),
            ([hot_row], hot_totals, 1),
        ]
    )

    with (
        patch.object(settings, "gateway_metrics_hybrid_read_enabled", True),
        patch.object(settings, "gateway_metrics_hybrid_merge_max_groups", 2000),
        patch(
            "domains.gateway.application.management.usage_metrics_router.compute_hot_cutoff",
            return_value=hot_cutoff,
        ),
    ):
        items, merged_totals, group_total = await router.aggregate_usage_statistics(
            axis,
            start,
            end,
            group_by=UsageStatisticsGroupBy.MODEL,
            filters=UsageStatisticsFilters(),
            page=1,
            page_size=20,
        )

    assert len(items) == 1
    assert items[0].requests == 5
    assert merged_totals.requests == 5
    assert group_total == 1
    assert hourly.aggregate_usage_statistics_by_axis.await_count == 2
    assert (
        hourly.aggregate_usage_statistics_by_axis.await_args_list[1].kwargs["fetch_all_groups"]
        is True
    )
    assert logs.aggregate_usage_statistics_by_axis.await_count == 2
    assert (
        logs.aggregate_usage_statistics_by_axis.await_args_list[1].kwargs["fetch_all_groups"]
        is True
    )


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_user_axis_falls_back_to_logs() -> None:
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.user(uuid.uuid4())
    expected = ([], _empty_totals(), 0)
    logs.aggregate_usage_statistics_by_axis = AsyncMock(return_value=expected)

    with patch.object(settings, "gateway_metrics_hybrid_read_enabled", True):
        result = await router.aggregate_usage_statistics(
            axis,
            datetime(2026, 6, 1, tzinfo=UTC),
            datetime(2026, 6, 10, tzinfo=UTC),
            group_by=UsageStatisticsGroupBy.MODEL,
            filters=UsageStatisticsFilters(),
            page=1,
            page_size=20,
        )

    assert result == expected
    logs.aggregate_usage_statistics_by_axis.assert_awaited_once()
    hourly.aggregate_usage_statistics_by_axis.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_statistics_cross_boundary_falls_back_when_too_many_groups() -> None:
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    hot_cutoff = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
    start = hot_cutoff - timedelta(days=1)
    end = datetime(2026, 6, 10, 15, 0, tzinfo=UTC)
    expected = ([], _empty_totals(), 0)
    hourly.aggregate_usage_statistics_by_axis = AsyncMock(return_value=([], _empty_totals(), 1500))
    logs.aggregate_usage_statistics_by_axis = AsyncMock(
        side_effect=[
            ([], _empty_totals(), 800),
            expected,
        ]
    )

    with (
        patch.object(settings, "gateway_metrics_hybrid_read_enabled", True),
        patch.object(settings, "gateway_metrics_hybrid_merge_max_groups", 2000),
        patch(
            "domains.gateway.application.management.usage_metrics_router.compute_hot_cutoff",
            return_value=hot_cutoff,
        ),
    ):
        result = await router.aggregate_usage_statistics(
            axis,
            start,
            end,
            group_by=UsageStatisticsGroupBy.CREDENTIAL,
            filters=UsageStatisticsFilters(),
            page=1,
            page_size=20,
        )

    assert result == expected
    assert hourly.aggregate_usage_statistics_by_axis.await_count == 1
    assert logs.aggregate_usage_statistics_by_axis.await_count == 2
    fallback_call = logs.aggregate_usage_statistics_by_axis.await_args_list[1]
    assert fallback_call.args[1] == start
    assert fallback_call.args[2] == end


@pytest.mark.asyncio
async def test_aggregate_summary_all_cold_loads_client_type_from_logs() -> None:
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 2, 0, 0, tzinfo=UTC)
    hot_cutoff = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    hourly.aggregate_summary_by_axis = AsyncMock(
        return_value={
            "total": 5,
            "input_tokens": 1,
            "output_tokens": 1,
            "cached_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": Decimal("0"),
            "success": 5,
            "failure": 0,
            "avg_latency_ms": 1.0,
            "avg_ttfb_ms": 1.0,
        }
    )
    logs.aggregate_by_client_type = AsyncMock(
        return_value=[{"client_type": "web", "requests": 5, "cost_usd": Decimal("0")}]
    )

    with (
        patch.object(settings, "gateway_metrics_hybrid_read_enabled", True),
        patch(
            "domains.gateway.application.management.usage_metrics_router.compute_hot_cutoff",
            return_value=hot_cutoff,
        ),
    ):
        summary = await router.aggregate_summary(axis, start, end)

    assert summary["by_client_type"][0]["client_type"] == "web"
    logs.aggregate_by_client_type.assert_awaited_once()
    hourly.aggregate_summary_by_axis.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregate_summary_client_type_filter_falls_back_to_logs() -> None:
    """client_type 筛选暂不支持 hourly rollup，应直接走明细 logs。"""
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    expected = {"total": 1, "success": 1, "failure": 0}
    logs.aggregate_summary_by_axis = AsyncMock(return_value={**expected, "by_client_type": []})
    logs.aggregate_by_client_type = AsyncMock(return_value=[])

    with patch.object(settings, "gateway_metrics_hybrid_read_enabled", True):
        result = await router.aggregate_summary(
            axis,
            start,
            end,
            client_type="model_connectivity_probe",
        )

    assert result["total"] == 1
    logs.aggregate_summary_by_axis.assert_awaited_once()
    call_kwargs = logs.aggregate_summary_by_axis.await_args.kwargs
    assert call_kwargs.get("client_type") == "model_connectivity_probe"
    hourly.aggregate_summary_by_axis.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_summary_status_filter_falls_back_to_logs() -> None:
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    expected = {"total": 1, "success": 1, "failure": 0, "by_client_type": []}
    logs.aggregate_summary_by_axis = AsyncMock(return_value={**expected, "by_client_type": []})
    logs.aggregate_by_client_type = AsyncMock(return_value=[])

    with patch.object(settings, "gateway_metrics_hybrid_read_enabled", True):
        result = await router.aggregate_summary(
            axis,
            start,
            end,
            status_filter="failed",
        )

    assert result["total"] == 1
    logs.aggregate_summary_by_axis.assert_awaited_once()
    hourly.aggregate_summary_by_axis.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_breakdown_pairs_cross_boundary_falls_back_when_too_many_groups() -> None:
    """冷热 pair 组数超过阈值时整窗 fallback 明细 logs。"""
    logs = MagicMock()
    hourly = MagicMock()
    router = UsageMetricsRouter(logs, hourly)
    axis = UsageAxis.workspace(uuid.uuid4())
    start = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 10, 0, 0, tzinfo=UTC)
    hot_cutoff = datetime(2026, 6, 9, 22, 0, tzinfo=UTC)
    parent_keys = [str(uuid.uuid4())]
    fallback_pairs = [
        BreakdownPairRow(parent_keys[0], uuid.uuid4(), "cred-a", 10),
    ]
    hot_pairs = [BreakdownPairRow(parent_keys[0], uuid.uuid4(), None, 1) for _ in range(10)]
    logs.aggregate_breakdown_pairs_by_axis = AsyncMock(
        side_effect=[hot_pairs, fallback_pairs],
    )
    hourly.aggregate_breakdown_pairs_by_axis = AsyncMock(
        return_value=[
            BreakdownPairRow(parent_keys[0], uuid.uuid4(), None, 1)
            for _ in range(1500)
        ]
    )

    with (
        patch.object(settings, "gateway_metrics_hybrid_read_enabled", True),
        patch.object(settings, "gateway_metrics_hybrid_merge_max_groups", 100),
        patch(
            "domains.gateway.application.management.usage_metrics_router.compute_hot_cutoff",
            return_value=hot_cutoff,
        ),
    ):
        result = await router.aggregate_breakdown_pairs(
            axis,
            start,
            end,
            parent_group_by=UsageStatisticsGroupBy.USER,
            breakdown_group_by=UsageStatisticsGroupBy.CREDENTIAL,
            parent_keys=parent_keys,
            filters=UsageStatisticsFilters(),
        )

    assert result == fallback_pairs
    assert logs.aggregate_breakdown_pairs_by_axis.await_count == 2
    fallback_call = logs.aggregate_breakdown_pairs_by_axis.await_args_list[1]
    assert fallback_call.args[1] == start
    assert fallback_call.args[2] == end
    hourly.aggregate_breakdown_pairs_by_axis.assert_awaited_once()
