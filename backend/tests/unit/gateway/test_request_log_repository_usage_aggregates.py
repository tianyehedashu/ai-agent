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

from domains.gateway.domain.usage.usage_axis import UsageAxis
from domains.gateway.domain.usage.usage_read_model import (
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
        cached_tokens=0,
        cache_creation_tokens=0,
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
        cached_tokens=0,
        cache_creation_tokens=0,
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
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0"),
        success=0,
        failure=0,
    )
    good = SimpleNamespace(
        credential_id=cid,
        requests=2,
        input_tokens=5,
        output_tokens=6,
        cached_tokens=0,
        cache_creation_tokens=0,
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
        cache_creation_tokens=0,
        cost_usd=Decimal("0.03"),
        avg_latency_ms=123.4,
        avg_ttfb_ms=42.0,
        cache_hit_count=1,
    )
    total_row = SimpleNamespace(
        group_total=1,
        requests=3,
        success_count=2,
        failure_count=1,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=4,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.03"),
        avg_latency_ms=123.4,
        avg_ttfb_ms=42.0,
        cache_hit_count=1,
    )
    item_result = MagicMock()
    item_result.all.return_value = [item_row]
    total_result = MagicMock()
    total_result.one.return_value = total_row
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[item_result, total_result])

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
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_by_axis_user_axis_splits_visibility_or() -> None:
    """user 轴将可见性 OR 拆成两段互斥查询，便于走部分索引。"""
    uid = uuid.uuid4()
    model_a = SimpleNamespace(
        group_key="gpt-4",
        label_snapshot=None,
        requests=2,
        success_count=2,
        failure_count=0,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.02"),
        avg_latency_ms=100.0,
        avg_ttfb_ms=30.0,
        cache_hit_count=0,
    )
    model_b = SimpleNamespace(
        group_key="gpt-4",
        label_snapshot=None,
        requests=1,
        success_count=1,
        failure_count=0,
        input_tokens=5,
        output_tokens=6,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.01"),
        avg_latency_ms=200.0,
        avg_ttfb_ms=50.0,
        cache_hit_count=0,
    )
    grouped_a = MagicMock()
    grouped_a.all.return_value = [model_a]
    grouped_b = MagicMock()
    grouped_b.all.return_value = [model_b]
    totals_a = MagicMock()
    totals_a.one.return_value = SimpleNamespace(
        requests=2,
        success_count=2,
        failure_count=0,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.02"),
        avg_latency_ms=100.0,
        avg_ttfb_ms=30.0,
        cache_hit_count=0,
    )
    totals_b = MagicMock()
    totals_b.one.return_value = SimpleNamespace(
        requests=1,
        success_count=1,
        failure_count=0,
        input_tokens=5,
        output_tokens=6,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.01"),
        avg_latency_ms=200.0,
        avg_ttfb_ms=50.0,
        cache_hit_count=0,
    )
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[grouped_a, grouped_b, totals_a, totals_b])

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    items, totals, group_total = await repo.aggregate_usage_statistics_by_axis(
        UsageAxis.user(uid),
        now - timedelta(days=7),
        now,
        group_by=UsageStatisticsGroupBy.MODEL,
        filters=UsageStatisticsFilters(),
        page=1,
        page_size=20,
    )

    assert session.execute.await_count == 4
    assert group_total == 1
    assert len(items) == 1
    assert items[0].requests == 3
    assert items[0].cost_usd == Decimal("0.03")
    assert totals.requests == 3
    assert totals.success_count == 3
    assert totals.avg_latency_ms == pytest.approx((100.0 * 2 + 200.0 * 1) / 3)

    compiled_sql = [
        str(call.args[0].compile(compile_kwargs={"literal_binds": True}))
        for call in session.execute.await_args_list
    ]
    assert any("vkey_id IS NULL" in sql and "vkey_id IS NOT NULL" not in sql for sql in compiled_sql)
    assert any("vkey_id IS NOT NULL" in sql and "vkey_id IS NULL" not in sql for sql in compiled_sql)


@pytest.mark.asyncio
async def test_aggregate_usage_statistics_user_model_credential_keeps_composite_groups() -> None:
    """user 轴拆查后，USER_MODEL_CREDENTIAL 不得按 user_id 单键合并。"""
    uid = uuid.uuid4()
    cred_a = uuid.uuid4()
    cred_b = uuid.uuid4()

    def _row(cred_id: uuid.UUID, requests: int, cost: str) -> SimpleNamespace:
        return SimpleNamespace(
            group_key=uid,
            label_snapshot="u@example.com",
            gk_1="gpt-4",
            ls_1=None,
            gk_2=cred_id,
            ls_2=f"Cred {cred_id.hex[:4]}",
            requests=requests,
            success_count=requests,
            failure_count=0,
            input_tokens=requests,
            output_tokens=requests,
            cached_tokens=0,
            cache_creation_tokens=0,
            cost_usd=Decimal(cost),
            avg_latency_ms=100.0,
            avg_ttfb_ms=30.0,
            cache_hit_count=0,
        )

    grouped_a = MagicMock()
    grouped_a.all.return_value = [_row(cred_a, 2, "0.02")]
    grouped_b = MagicMock()
    grouped_b.all.return_value = [_row(cred_b, 3, "0.03")]
    totals_a = MagicMock()
    totals_a.one.return_value = SimpleNamespace(
        requests=2,
        success_count=2,
        failure_count=0,
        input_tokens=2,
        output_tokens=2,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.02"),
        avg_latency_ms=100.0,
        avg_ttfb_ms=30.0,
        cache_hit_count=0,
    )
    totals_b = MagicMock()
    totals_b.one.return_value = SimpleNamespace(
        requests=3,
        success_count=3,
        failure_count=0,
        input_tokens=3,
        output_tokens=3,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.03"),
        avg_latency_ms=100.0,
        avg_ttfb_ms=30.0,
        cache_hit_count=0,
    )
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[grouped_a, grouped_b, totals_a, totals_b])

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    items, totals, group_total = await repo.aggregate_usage_statistics_by_axis(
        UsageAxis.user(uid),
        now - timedelta(days=7),
        now,
        group_by=UsageStatisticsGroupBy.USER_MODEL_CREDENTIAL,
        filters=UsageStatisticsFilters(),
        page=1,
        page_size=20,
    )

    assert session.execute.await_count == 4
    assert group_total == 2
    assert len(items) == 2
    assert {item.requests for item in items} == {2, 3}
    assert totals.requests == 5
    assert totals.cost_usd == Decimal("0.05")


@pytest.mark.asyncio
async def test_aggregate_summary_by_axis_user_axis_splits_visibility_or() -> None:
    uid = uuid.uuid4()
    row_a = SimpleNamespace(
        total=4,
        input_tokens=40,
        output_tokens=80,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.04"),
        success=4,
        failure=0,
        avg_latency=100.0,
        avg_ttfb=20.0,
    )
    row_b = SimpleNamespace(
        total=1,
        input_tokens=10,
        output_tokens=20,
        cached_tokens=0,
        cache_creation_tokens=0,
        cost_usd=Decimal("0.01"),
        success=1,
        failure=0,
        avg_latency=300.0,
        avg_ttfb=60.0,
    )
    result_a = MagicMock()
    result_a.one.return_value = row_a
    result_b = MagicMock()
    result_b.one.return_value = row_b
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[result_a, result_b])

    repo = RequestLogRepository(session)
    now = datetime.now(UTC)
    summary = await repo.aggregate_summary_by_axis(
        UsageAxis.user(uid),
        now - timedelta(days=7),
        now,
    )

    assert session.execute.await_count == 2
    assert summary["total"] == 5
    assert summary["success"] == 5
    assert summary["cost_usd"] == Decimal("0.05")
    assert summary["avg_latency_ms"] == pytest.approx((100.0 * 4 + 300.0 * 1) / 5)

    compiled_sql = [
        str(call.args[0].compile(compile_kwargs={"literal_binds": True}))
        for call in session.execute.await_args_list
    ]
    assert any("vkey_id IS NULL" in sql and "vkey_id IS NOT NULL" not in sql for sql in compiled_sql)
    assert any("vkey_id IS NOT NULL" in sql and "vkey_id IS NULL" not in sql for sql in compiled_sql)
