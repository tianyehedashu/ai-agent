"""budget_usage_persist 幂等 + 合并记录单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application import budget_usage_persist as mod
from domains.gateway.domain.quota_plan import PLATFORM_NS


@pytest.mark.asyncio
async def test_bucket_record_skipped_without_request_id(monkeypatch) -> None:
    record = MagicMock()
    monkeypatch.setattr(mod, "record_bucket_usage", record)
    acquire = AsyncMock()
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", acquire)

    await mod.schedule_platform_budget_usage_upsert(
        items=[mod.PlatformBudgetUpsertItem(budget_id=uuid.uuid4(), period="daily")],
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

    await mod.schedule_platform_budget_usage_upsert(
        items=[mod.PlatformBudgetUpsertItem(budget_id=uuid.uuid4(), period="daily")],
        delta_tokens=100,
        delta_cost_usd=Decimal("0.01"),
        delta_requests=1,
        request_id="req-dup",
        source="proxy",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    record.assert_not_called()


@pytest.mark.asyncio
async def test_bucket_record_on_acquire(monkeypatch) -> None:
    budget_id = uuid.uuid4()
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", AsyncMock(return_value=True))
    record = MagicMock()
    monkeypatch.setattr(mod, "record_bucket_usage", record)

    await mod.schedule_platform_budget_usage_upsert(
        items=[mod.PlatformBudgetUpsertItem(budget_id=budget_id, period="daily")],
        delta_tokens=50,
        delta_cost_usd=Decimal("0.02"),
        delta_requests=1,
        request_id="req-ok",
        source="proxy",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    record.assert_called_once()
    args, kwargs = record.call_args
    assert args[0] == PLATFORM_NS
    assert args[1] == budget_id
    assert args[2] == budget_id
    assert isinstance(args[3], datetime)
    assert kwargs == {
        "delta_tokens": 50,
        "delta_cost_usd": Decimal("0.02"),
        "delta_requests": 1,
    }


@pytest.mark.asyncio
async def test_proxy_and_callback_sources_both_acquire(monkeypatch) -> None:
    acquire = AsyncMock(side_effect=[True, True])
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", acquire)
    record = MagicMock()
    monkeypatch.setattr(mod, "record_bucket_usage", record)

    budget_id = uuid.uuid4()
    item = mod.PlatformBudgetUpsertItem(budget_id=budget_id, period="daily")
    settled = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)

    await mod.schedule_platform_budget_usage_upsert(
        items=[item],
        delta_tokens=50,
        delta_cost_usd=Decimal("0"),
        delta_requests=1,
        request_id="req-defer",
        source="proxy",
        settled_at=settled,
    )
    await mod.schedule_platform_budget_usage_upsert(
        items=[item],
        delta_tokens=0,
        delta_cost_usd=Decimal("0.05"),
        delta_requests=0,
        request_id="req-defer",
        source="callback",
        settled_at=settled,
    )

    assert acquire.await_count == 2
    assert acquire.await_args_list[0].args == (PLATFORM_NS, "req-defer", "proxy")
    assert acquire.await_args_list[1].args == (PLATFORM_NS, "req-defer", "callback")
    assert record.call_count == 2
