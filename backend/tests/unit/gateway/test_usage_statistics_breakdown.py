"""调用统计行内 breakdown 单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.domain.usage_read_model import (
    UsageAggregation,
    UsageStatisticsBreakdownBy,
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    BreakdownPairRow,
    RequestLogUsageAggregateRow,
)
from domains.tenancy.domain.management_context import ManagementTeamContext


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_breakdown_computes_share() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    member_id = uuid.uuid4()
    cred_a = uuid.uuid4()
    cred_b = uuid.uuid4()
    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="admin",
        user_id=user_id,
        is_platform_admin=False,
    )
    svc._logs.count_usage_requests_by_axis = AsyncMock(return_value=100)
    svc._logs.aggregate_usage_statistics_by_axis = AsyncMock(
        return_value=(
            [
                RequestLogUsageAggregateRow(
                    group_key=cred_a,
                    label_snapshot=None,
                    requests=60,
                    success_count=60,
                    failure_count=0,
                    input_tokens=1,
                    output_tokens=1,
                    cached_tokens=0,
                    cost_usd=Decimal("0.01"),
                    avg_latency_ms=10.0,
                    cache_hit_count=0,
                ),
                RequestLogUsageAggregateRow(
                    group_key=cred_b,
                    label_snapshot=None,
                    requests=40,
                    success_count=40,
                    failure_count=0,
                    input_tokens=1,
                    output_tokens=1,
                    cached_tokens=0,
                    cost_usd=Decimal("0.01"),
                    avg_latency_ms=10.0,
                    cache_hit_count=0,
                ),
            ],
            MagicMock(),
            2,
        )
    )
    svc._creds.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(id=cred_a, name="凭据 A"),
            SimpleNamespace(id=cred_b, name="凭据 B"),
        ]
    )
    svc._system_creds.list_by_ids = AsyncMock(return_value=[])

    now = datetime.now(UTC)
    with patch.object(settings, "gateway_metrics_hybrid_read_enabled", False):
        summary = await svc.aggregate_usage_statistics_breakdown(
            ctx,
            now,
            now,
            usage_aggregation=UsageAggregation.WORKSPACE,
            filters=UsageStatisticsFilters(),
            parent_group_by=UsageStatisticsGroupBy.USER,
            parent_group_key=str(member_id),
            breakdown_by=UsageStatisticsBreakdownBy.CREDENTIAL,
            top_n=3,
        )

    assert summary.parent_requests == 100
    assert len(summary.items) == 2
    assert summary.items[0].label == "凭据 A"
    assert summary.items[0].share == pytest.approx(0.6)
    assert summary.items[1].share == pytest.approx(0.4)
    svc._logs.count_usage_requests_by_axis.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_breakdown_batch_groups_per_parent() -> None:
    """批量 breakdown：一次聚合多个父行，按父键分组并算 share，含未关联分桶。"""
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    parent_a = uuid.uuid4()
    parent_b = uuid.uuid4()
    cred_a = uuid.uuid4()
    cred_b = uuid.uuid4()
    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="admin",
        user_id=user_id,
        is_platform_admin=False,
    )
    svc._usage_metrics.aggregate_breakdown_pairs = AsyncMock(
        return_value=[
            BreakdownPairRow(str(parent_a), cred_a, None, 30),
            BreakdownPairRow(str(parent_a), cred_b, None, 10),
            BreakdownPairRow(str(parent_a), None, None, 10),  # 未关联凭据分桶
            BreakdownPairRow(str(parent_b), cred_a, None, 5),
        ]
    )
    svc._creds.list_by_ids = AsyncMock(
        return_value=[
            SimpleNamespace(id=cred_a, name="凭据 A"),
            SimpleNamespace(id=cred_b, name="凭据 B"),
        ]
    )
    svc._system_creds.list_by_ids = AsyncMock(return_value=[])

    now = datetime.now(UTC)
    summary = await svc.aggregate_usage_statistics_breakdown_batch(
        ctx,
        now,
        now,
        usage_aggregation=UsageAggregation.WORKSPACE,
        filters=UsageStatisticsFilters(),
        parent_group_by=UsageStatisticsGroupBy.USER,
        parent_keys=[str(parent_a), str(parent_b)],
        breakdown_by=UsageStatisticsBreakdownBy.CREDENTIAL,
        top_n=2,
    )

    assert [it.parent_group_key for it in summary.items] == [str(parent_a), str(parent_b)]
    item_a = summary.items[0]
    # 父键总请求数 = 全部分桶之和（含未关联）
    assert item_a.parent_requests == 50
    # top_n=2：取请求最高的两项（凭据 A=30、未关联=10 与凭据 B=10 同分取前二）
    assert len(item_a.items) == 2
    assert item_a.items[0].label == "凭据 A"
    assert item_a.items[0].share == pytest.approx(0.6)

    item_b = summary.items[1]
    assert item_b.parent_requests == 5
    assert item_b.items[0].label == "凭据 A"
    assert item_b.items[0].share == pytest.approx(1.0)
