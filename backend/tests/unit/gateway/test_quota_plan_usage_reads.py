"""QuotaPlanUsageReadService 单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

import domains.gateway.application.quota.management.quota_plan_usage_reads as reads_mod
from domains.gateway.application.quota.management.quota_plan_usage_reads import (
    QuotaPlanUsageReadService,
    QuotaUsageTotals,
    QuotaWindowLookup,
    resolve_quota_window_key,
)
from domains.gateway.domain.quota.period_reset_anchor import PeriodResetAnchor
from domains.gateway.domain.quota.quota_plan import PROVIDER_NS
from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
    GatewayQuotaPlanUsageBucket,
)


@pytest.mark.asyncio
async def test_batch_usage_reads_bucket_row() -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    window_start = datetime(2026, 6, 20, tzinfo=UTC)
    lookup = QuotaWindowLookup(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        quota_id=quota_id,
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        plan_valid_from=None,
    )
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    key = resolve_quota_window_key(lookup, now=now)
    assert key.window_start == window_start

    bucket_row = GatewayQuotaPlanUsageBucket(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        quota_id=quota_id,
        window_start=window_start,
        tokens=150,
        requests=2,
        cost_usd=Decimal("0.5"),
    )
    service = QuotaPlanUsageReadService(MagicMock())
    service._load_buckets = AsyncMock(return_value={key: bucket_row})  # type: ignore[method-assign]
    service._aggregate_logs = AsyncMock()  # type: ignore[method-assign]

    totals = await service.batch_usage_for_quota_windows([lookup], now=now)
    assert totals[key] == QuotaUsageTotals(Decimal("0.5"), 150, 2)
    service._aggregate_logs.assert_not_called()


@pytest.mark.asyncio
async def test_aggregate_logs_counts_only_success(monkeypatch) -> None:
    """logs fallback 仅统计 success，与 Redis 结算语义一致。"""
    from domains.gateway.application.quota.management import quota_plan_usage_reads as reads_mod

    captured: list[object] = []

    class _Session:
        async def execute(self, stmt: object) -> object:
            captured.append(stmt)
            row = MagicMock()
            row.tokens = 0
            row.requests = 0
            row.cost_usd = 0
            return MagicMock(one=lambda: row)

    plan_id = uuid.uuid4()
    window_start = datetime(2026, 6, 20, tzinfo=UTC)
    service = reads_mod.QuotaPlanUsageReadService(_Session())  # type: ignore[arg-type]
    log_key = reads_mod._LogWindowKey(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        window_start=window_start,
    )
    await service._aggregate_logs([log_key], until=datetime(2026, 6, 20, 12, 0, tzinfo=UTC))

    assert captured
    compiled = str(captured[0])
    assert "gateway_request_logs.status" in compiled


@pytest.mark.asyncio
async def test_batch_usage_falls_back_to_request_logs() -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    window_start = datetime(2026, 6, 20, tzinfo=UTC)
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    lookup = QuotaWindowLookup(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        quota_id=quota_id,
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        plan_valid_from=None,
    )
    key = resolve_quota_window_key(lookup, now=now)

    service = QuotaPlanUsageReadService(MagicMock())
    service._load_buckets = AsyncMock(return_value={})  # type: ignore[method-assign]
    service._aggregate_logs = AsyncMock(  # type: ignore[method-assign]
        return_value={
            reads_mod._LogWindowKey(
                ns=PROVIDER_NS,
                plan_id=plan_id,
                window_start=window_start,
            ): QuotaUsageTotals(Decimal("0.2"), 50, 1),
        }
    )

    totals = await service.batch_usage_for_quota_windows([lookup], now=now)
    assert totals[key] == QuotaUsageTotals(Decimal("0.2"), 50, 1)


@pytest.mark.asyncio
async def test_rolling_skips_bucket_and_uses_logs() -> None:
    """滚动窗口不查 PG 桶（口径错位会低估），直接按 [window_start, now] 聚合日志。"""
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    lookup = QuotaWindowLookup(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        quota_id=quota_id,
        window_seconds=18000,
        reset_strategy="rolling",
        plan_valid_from=None,
    )
    key = resolve_quota_window_key(lookup, now=now)

    service = QuotaPlanUsageReadService(MagicMock())
    # 即便桶里有值（当前分钟的单条），滚动也应忽略它而走日志。
    service._load_buckets = AsyncMock(return_value={})  # type: ignore[method-assign]
    service._aggregate_logs = AsyncMock(  # type: ignore[method-assign]
        return_value={
            reads_mod._LogWindowKey(
                ns=PROVIDER_NS,
                plan_id=plan_id,
                window_start=key.window_start,
            ): QuotaUsageTotals(Decimal("3.0"), 900, 9),
        }
    )

    totals = await service.batch_usage_for_quota_windows([lookup], now=now)
    assert totals[key] == QuotaUsageTotals(Decimal("3.0"), 900, 9)
    # 滚动键不进 _load_buckets 查询参数。
    loaded_keys = service._load_buckets.call_args.args[0]
    assert loaded_keys == []
    service._aggregate_logs.assert_called_once()


@pytest.mark.asyncio
async def test_batch_usage_uses_custom_period_reset_anchor() -> None:
    """自定义锚点下 bucket 键与 resolve_quota_window_key 一致。"""
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    anchor = PeriodResetAnchor(timezone="Asia/Shanghai", time_minutes=9 * 60, day_of_month=1)
    lookup = QuotaWindowLookup(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        quota_id=quota_id,
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        plan_valid_from=None,
        period_reset_anchor=anchor,
    )
    now = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)
    key = resolve_quota_window_key(lookup, now=now)
    assert key.window_start == datetime(2026, 6, 20, 1, 0, tzinfo=UTC)

    bucket_row = GatewayQuotaPlanUsageBucket(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        quota_id=quota_id,
        window_start=key.window_start,
        tokens=10,
        requests=1,
        cost_usd=Decimal("0.1"),
    )
    service = QuotaPlanUsageReadService(MagicMock())
    service._load_buckets = AsyncMock(return_value={key: bucket_row})  # type: ignore[method-assign]
    service._aggregate_logs = AsyncMock()  # type: ignore[method-assign]

    totals = await service.batch_usage_for_quota_windows([lookup], now=now)
    assert totals[key] == QuotaUsageTotals(Decimal("0.1"), 10, 1)
