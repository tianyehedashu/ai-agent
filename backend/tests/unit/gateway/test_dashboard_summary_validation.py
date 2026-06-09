"""Dashboard /summary 路由参数校验单测。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.usage_reads import (
    UsageStatisticsBreakdownSummary,
    UsageStatisticsMetric,
    UsageStatisticsSummary,
)
from domains.gateway.domain.usage_read_model import (
    UsageAggregation,
    UsageStatisticsBreakdownBy,
    UsageStatisticsGroupBy,
)
from domains.gateway.presentation.routers.dashboard import (
    dashboard_statistics,
    dashboard_statistics_breakdown,
    dashboard_summary,
)
from domains.tenancy.domain.management_context import ManagementTeamContext
from libs.api.pagination import PageParams
from libs.exceptions import ValidationError


@pytest.fixture
def fake_team():
    return ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="shared",
        team_role="admin",
        user_id=uuid.uuid4(),
        is_platform_admin=True,
    )


@pytest.fixture
def fake_reads():
    reads = MagicMock()
    now = datetime.now(UTC)
    empty_metric = UsageStatisticsMetric(
        requests=0,
        success_count=0,
        failure_count=0,
        input_tokens=0,
        output_tokens=0,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0"),
        avg_latency_ms=0.0,
        avg_ttfb_ms=0.0,
        cache_hit_count=0,
    )
    reads.aggregate_request_log_summary = AsyncMock(
        return_value={
            "total": 10,
            "input_tokens": 100,
            "output_tokens": 200,
            "cost_usd": Decimal("0.1"),
            "success": 8,
            "failure": 2,
            "avg_latency_ms": 150.0,
            "avg_ttfb_ms": 42.0,
            "by_client_type": [],
        }
    )
    reads.aggregate_usage_statistics = AsyncMock(
        return_value=(
            UsageStatisticsSummary(
                start=now,
                end=now,
                group_by=UsageStatisticsGroupBy.CREDENTIAL,
                totals=empty_metric,
                items=[],
            ),
            0,
        )
    )
    reads.aggregate_usage_statistics_breakdown = AsyncMock(
        return_value=UsageStatisticsBreakdownSummary(
            parent_group_by=UsageStatisticsGroupBy.USER,
            parent_group_key="",
            breakdown_by=UsageStatisticsBreakdownBy.CREDENTIAL,
            parent_requests=0,
            items=[],
        )
    )
    return reads


@pytest.mark.asyncio
async def test_dashboard_summary_rejects_inverted_date_range(fake_team, fake_reads) -> None:
    """start > end 时应返回 422 错误。"""
    end = datetime.now(UTC)
    start = end + timedelta(days=1)
    with pytest.raises(ValidationError) as exc_info:
        await dashboard_summary(
            team=fake_team,
            reads=fake_reads,
            days=7,
            start=start,
            end=end,
        )
    assert "start must be before or equal to end" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dashboard_summary_accepts_equal_dates(fake_team, fake_reads) -> None:
    """start == end 时应允许通过。"""
    now = datetime.now(UTC)
    result = await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        start=now,
        end=now,
        status_filter=None,
        capability=None,
        model=None,
    )
    assert result.total_requests == 10


@pytest.mark.asyncio
async def test_dashboard_summary_strips_whitespace_from_status(fake_team, fake_reads) -> None:
    """status_filter 前后空格应被 strip。"""
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        status_filter="  success  ",
        capability=None,
        model=None,
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["status_filter"] == "success"


@pytest.mark.asyncio
async def test_dashboard_summary_strips_whitespace_from_capability(fake_team, fake_reads) -> None:
    """capability 前后空格应被 strip。"""
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        capability="  chat  ",
        status_filter=None,
        model=None,
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["capability"] == "chat"


@pytest.mark.asyncio
async def test_dashboard_summary_strips_whitespace_from_model(fake_team, fake_reads) -> None:
    """model 前后空格应被 strip。"""
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        model="  gpt-4  ",
        status_filter=None,
        capability=None,
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_dashboard_summary_passes_all_filter_params(fake_team, fake_reads) -> None:
    """所有筛选参数应正确透传给 aggregate_request_log_summary。"""
    uid = uuid.uuid4()
    cid = uuid.uuid4()
    vid = uuid.uuid4()
    start = datetime.now(UTC) - timedelta(days=1)
    end = datetime.now(UTC)
    await dashboard_summary(
        team=fake_team,
        reads=fake_reads,
        days=7,
        start=start,
        end=end,
        status_filter="failed",
        capability="chat",
        vkey_id=vid,
        credential_id=cid,
        user_id=uid,
        model="gpt-4",
    )
    call_kwargs = fake_reads.aggregate_request_log_summary.await_args.kwargs
    assert call_kwargs["status_filter"] == "failed"
    assert call_kwargs["capability"] == "chat"
    assert call_kwargs["vkey_id"] == vid
    assert call_kwargs["credential_id"] == cid
    assert call_kwargs["user_id"] == uid
    assert call_kwargs["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_dashboard_statistics_uses_explicit_date_range(fake_team, fake_reads) -> None:
    """statistics 应优先使用 start/end，而不是 days 默认窗口。"""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 31, tzinfo=UTC)

    await dashboard_statistics(
        team=fake_team,
        reads=fake_reads,
        page=PageParams(),
        days=7,
        usage_aggregation=UsageAggregation.WORKSPACE,
        start=start,
        end=end,
        group_by=UsageStatisticsGroupBy.MODEL,
        credential_id=None,
        user_id=None,
        filter_team_id=None,
        model=None,
        provider=None,
        capability=None,
        status_filter=None,
        vkey_id=None,
    )

    call_args = fake_reads.aggregate_usage_statistics.await_args
    assert call_args.args[1] == start
    assert call_args.args[2] == end


@pytest.mark.asyncio
async def test_dashboard_statistics_rejects_inverted_date_range(fake_team, fake_reads) -> None:
    """statistics start > end 时应返回 422 错误。"""
    end = datetime(2026, 1, 1, tzinfo=UTC)
    start = end + timedelta(days=1)

    with pytest.raises(ValidationError) as exc_info:
        await dashboard_statistics(
            team=fake_team,
            reads=fake_reads,
            page=PageParams(),
            days=7,
            usage_aggregation=UsageAggregation.WORKSPACE,
            start=start,
            end=end,
            group_by=UsageStatisticsGroupBy.CREDENTIAL,
            credential_id=None,
            user_id=None,
            filter_team_id=None,
            model=None,
            provider=None,
            capability=None,
            status_filter=None,
            vkey_id=None,
        )

    assert "start must be before or equal to end" in str(exc_info.value)
    fake_reads.aggregate_usage_statistics.assert_not_awaited()


@pytest.mark.asyncio
async def test_dashboard_statistics_breakdown_uses_explicit_date_range(
    fake_team, fake_reads
) -> None:
    """breakdown 应与主统计使用同一个 start/end 窗口。"""
    start = datetime(2026, 2, 1, tzinfo=UTC)
    end = datetime(2026, 2, 8, tzinfo=UTC)

    await dashboard_statistics_breakdown(
        team=fake_team,
        reads=fake_reads,
        days=7,
        usage_aggregation=UsageAggregation.WORKSPACE,
        start=start,
        end=end,
        parent_group_by=UsageStatisticsGroupBy.USER,
        parent_group_key=str(uuid.uuid4()),
        breakdown_by=UsageStatisticsBreakdownBy.CREDENTIAL,
        top_n=3,
        credential_id=None,
        user_id=None,
        filter_team_id=None,
        model=None,
        provider=None,
        capability=None,
        status_filter=None,
        vkey_id=None,
    )

    call_args = fake_reads.aggregate_usage_statistics_breakdown.await_args
    assert call_args.args[1] == start
    assert call_args.args[2] == end
