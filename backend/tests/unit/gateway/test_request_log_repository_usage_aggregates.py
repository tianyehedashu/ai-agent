"""RequestLogRepository 用量聚合（route / deployment / credential）单测。

Stage 2 起：仓储 5 对镜像方法收敛为 5 个 axis-based 方法；本套测试基于 ``UsageAxis``
工厂方法构造维度。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.domain.usage_read_model import (
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    RequestLogRepository,
)


@pytest.mark.asyncio
async def test_aggregate_by_route_names_workspace_empty_skips_execute() -> None:
    session = AsyncMock(spec=["execute"])
    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    out = await repo.aggregate_by_route_names_by_axis(
        UsageAxis.workspace(uuid.uuid4()), [], now, now
    )
    assert out == {}
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_by_deployment_ids_workspace_empty_skips_execute() -> None:
    session = AsyncMock(spec=["execute"])
    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    out = await repo.aggregate_by_deployment_ids_by_axis(
        UsageAxis.workspace(uuid.uuid4()), [], now, now
    )
    assert out == {}
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_by_route_names_workspace_fills_defaults_and_rows() -> None:
    team_id = uuid.uuid4()
    session = AsyncMock()
    row = SimpleNamespace(
        route_name="m-a",
        requests=3,
        input_tokens=10,
        output_tokens=20,
        cost_usd=Decimal("0.05"),
    )
    result = MagicMock()
    result.all.return_value = [row]
    session.execute = AsyncMock(return_value=result)
    repo = RequestLogRepository(session)
    start = datetime.now(UTC) - timedelta(days=1)
    end = datetime.now(UTC)
    out = await repo.aggregate_by_route_names_by_axis(
        UsageAxis.workspace(team_id), ["m-a", "m-b"], start, end
    )
    assert out["m-a"]["requests"] == 3
    assert out["m-a"]["cost_usd"] == Decimal("0.05")
    assert out["m-b"]["requests"] == 0
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregate_by_deployment_ids_user_axis_maps_by_id() -> None:
    user_id = uuid.uuid4()
    mid = uuid.uuid4()
    session = AsyncMock()
    row = SimpleNamespace(
        deployment_gateway_model_id=mid,
        requests=1,
        input_tokens=2,
        output_tokens=3,
        cost_usd=Decimal("0.01"),
    )
    result = MagicMock()
    result.all.return_value = [row]
    session.execute = AsyncMock(return_value=result)
    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    out = await repo.aggregate_by_deployment_ids_by_axis(UsageAxis.user(user_id), [mid], now, now)
    assert out[mid]["requests"] == 1
    assert out[mid]["input_tokens"] == 2


@pytest.mark.asyncio
async def test_aggregate_by_credential_global_skips_null_credential_id_rows() -> None:
    cid = uuid.uuid4()
    session = AsyncMock()
    bad = SimpleNamespace(
        credential_id=None,
        requests=99,
        input_tokens=0,
        output_tokens=0,
        cost_usd=Decimal("0"),
        success=0,
        failure=0,
    )
    good = SimpleNamespace(
        credential_id=cid,
        requests=2,
        input_tokens=5,
        output_tokens=6,
        cost_usd=Decimal("0.02"),
        success=1,
        failure=1,
    )
    result = MagicMock()
    result.all.return_value = [bad, good]
    session.execute = AsyncMock(return_value=result)
    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    out = await repo.aggregate_by_credential_global(now - timedelta(hours=1), now)
    assert list(out.keys()) == [cid]
    assert out[cid]["requests"] == 2
    assert out[cid]["success"] == 1
    assert out[cid]["failure"] == 1


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_by_axis_maps_items_and_totals() -> None:
    cid = uuid.uuid4()
    item_row = SimpleNamespace(
        group_key=cid,
        label_snapshot="历史凭据",
        requests=3,
        success_count=2,
        failure_count=1,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=4,
        cost_usd=Decimal("0.03"),
        avg_latency_ms=123.4,
        cache_hit_count=1,
    )
    total_row = SimpleNamespace(
        requests=3,
        success_count=2,
        failure_count=1,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=4,
        cost_usd=Decimal("0.03"),
        avg_latency_ms=123.4,
        cache_hit_count=1,
    )
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1
    item_result = MagicMock()
    item_result.all.return_value = [item_row]
    total_result = MagicMock()
    total_result.one.return_value = total_row
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[count_result, item_result, total_result])

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    items, totals, group_total = await repo.aggregate_usage_statistics_by_axis(
        UsageAxis.workspace(uuid.uuid4()),
        now - timedelta(days=1),
        now,
        group_by=UsageStatisticsGroupBy.CREDENTIAL,
        filters=UsageStatisticsFilters(provider="openai"),
        page=1,
        page_size=10,
    )

    assert len(items) == 1
    assert group_total == 1
    assert items[0].group_key == cid
    assert items[0].requests == 3
    assert items[0].cost_usd == Decimal("0.03")
    assert totals.success_count == 2
    assert totals.cached_tokens == 4
    assert session.execute.await_count == 3
