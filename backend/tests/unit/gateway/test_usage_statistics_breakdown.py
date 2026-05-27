"""调用统计行内 breakdown 单测。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.domain.usage_read_model import (
    UsageAggregation,
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
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

    now = MagicMock()
    summary = await svc.aggregate_usage_statistics_breakdown(
        ctx,
        now,
        now,
        usage_aggregation=UsageAggregation.WORKSPACE,
        filters=UsageStatisticsFilters(),
        parent_group_by=UsageStatisticsGroupBy.USER,
        parent_group_key=str(member_id),
        breakdown_by=UsageStatisticsGroupBy.CREDENTIAL,
        top_n=3,
    )

    assert summary.parent_requests == 100
    assert len(summary.items) == 2
    assert summary.items[0].label == "凭据 A"
    assert summary.items[0].share == pytest.approx(0.6)
    assert summary.items[1].share == pytest.approx(0.4)
    svc._logs.count_usage_requests_by_axis.assert_awaited_once()
