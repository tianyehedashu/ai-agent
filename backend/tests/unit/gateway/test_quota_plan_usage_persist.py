"""quota_plan_usage_persist 幂等 + 合并记录单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application import quota_plan_usage_persist as mod
from domains.gateway.domain.quota_plan import PROVIDER_NS, PlanQuotaSpec


def _daily_spec() -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="daily",
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        limit_tokens=1_000_000,
    )


@pytest.mark.asyncio
async def test_bucket_record_skipped_without_request_id(monkeypatch) -> None:
    record = MagicMock()
    monkeypatch.setattr(mod, "record_bucket_usage", record)
    acquire = AsyncMock()
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", acquire)

    await mod.schedule_quota_plan_usage_upsert(
        ns=PROVIDER_NS,
        plan_id=uuid.uuid4(),
        specs=[_daily_spec()],
        delta_tokens=1,
        delta_cost_usd=Decimal("0"),
        request_id=None,
    )

    acquire.assert_not_called()
    record.assert_not_called()


@pytest.mark.asyncio
async def test_bucket_record_skipped_when_idempotency_key_exists(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", AsyncMock(return_value=False))
    record = MagicMock()
    monkeypatch.setattr(mod, "record_bucket_usage", record)

    await mod.schedule_quota_plan_usage_upsert(
        ns=PROVIDER_NS,
        plan_id=uuid.uuid4(),
        specs=[_daily_spec()],
        delta_tokens=100,
        delta_cost_usd=Decimal("0"),
        delta_requests=1,
        request_id="req-dup",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    record.assert_not_called()


@pytest.mark.asyncio
async def test_rolling_spec_skips_bucket_persist(monkeypatch) -> None:
    """滚动窗口不落 PG 桶：连幂等键都不应获取，record 不调用。"""
    acquire = AsyncMock(return_value=True)
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", acquire)
    record = MagicMock()
    monkeypatch.setattr(mod, "record_bucket_usage", record)

    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="5h",
        window_seconds=18000,
        reset_strategy="rolling",
        limit_tokens=1_000_000,
    )
    await mod.schedule_quota_plan_usage_upsert(
        ns=PROVIDER_NS,
        plan_id=uuid.uuid4(),
        specs=[spec],
        delta_tokens=100,
        delta_cost_usd=Decimal("0"),
        delta_requests=1,
        request_id="req-rolling",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    acquire.assert_not_called()
    record.assert_not_called()


@pytest.mark.asyncio
async def test_bucket_record_on_acquire(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    spec = _daily_spec()
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", AsyncMock(return_value=True))
    record = MagicMock()
    monkeypatch.setattr(mod, "record_bucket_usage", record)

    await mod.schedule_quota_plan_usage_upsert(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        specs=[spec],
        delta_tokens=10,
        delta_cost_usd=Decimal("0.03"),
        delta_requests=1,
        request_id="req-ok",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    record.assert_called_once()
    args, kwargs = record.call_args
    assert args[0] == PROVIDER_NS
    assert args[1] == plan_id
    assert args[2] == spec.quota_id
    assert isinstance(args[3], datetime)
    assert kwargs == {
        "delta_tokens": 10,
        "delta_cost_usd": Decimal("0.03"),
        "delta_requests": 1,
        "delta_images": 0,
    }
