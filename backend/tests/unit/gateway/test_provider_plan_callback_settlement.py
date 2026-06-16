"""ProviderPlan callback 结算单测。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application import provider_plan_callback_settlement as mod
from domains.gateway.domain.quota_plan import PlanQuotaSpec


@pytest.mark.asyncio
async def test_commit_provider_plan_on_success(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=quota_id,
        label="24h",
        window_seconds=86400,
        limit_tokens=4_000_000,
    )

    guard = MagicMock()
    guard.commit = AsyncMock()
    guard.release = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_plan_guard", lambda: guard)
    monkeypatch.setattr(mod, "_load_plan_specs", AsyncMock(return_value={quota_id: spec}))
    monkeypatch.setattr(mod, "_acquire_once", AsyncMock(return_value=True))
    schedule = MagicMock()
    monkeypatch.setattr(mod, "schedule_quota_plan_usage_upsert", schedule)

    await mod.settle_provider_plan_from_callback(
        metadata={"gateway_provider_plan_id": str(plan_id)},
        status="success",
        cost_usd=Decimal("0"),
        total_tokens=12_345,
        request_id="req-1",
    )

    guard.commit.assert_awaited_once_with(
        plan_id,
        [spec],
        delta_tokens=12_345,
        delta_usd=Decimal("0"),
    )
    guard.release.assert_not_awaited()
    schedule.assert_called_once()


@pytest.mark.asyncio
async def test_release_provider_plan_on_failure(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=quota_id,
        label="24h",
        window_seconds=86400,
        limit_tokens=4_000_000,
    )

    guard = MagicMock()
    guard.commit = AsyncMock()
    guard.release = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_plan_guard", lambda: guard)
    monkeypatch.setattr(mod, "_load_plan_specs", AsyncMock(return_value={quota_id: spec}))
    monkeypatch.setattr(mod, "_acquire_once", AsyncMock(return_value=True))

    await mod.settle_provider_plan_from_callback(
        metadata={
            "gateway_provider_plan_id": str(plan_id),
            "gateway_provider_plan_reservations": [
                {"quota_id": str(quota_id), "minute_unix": 1, "reserved_requests": 1},
            ],
        },
        status="failed",
        cost_usd=Decimal("0"),
        total_tokens=0,
        request_id="req-2",
    )

    guard.release.assert_awaited_once()
    guard.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_skipped_without_plan_id(monkeypatch) -> None:
    guard = MagicMock()
    guard.commit = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_plan_guard", lambda: guard)

    await mod.settle_provider_plan_from_callback(
        metadata={},
        status="success",
        cost_usd=Decimal("1"),
        total_tokens=100,
        request_id="req-3",
    )

    guard.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_skipped_when_idempotent(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(quota_id=quota_id, label="24h", window_seconds=86400)

    guard = MagicMock()
    guard.commit = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_plan_guard", lambda: guard)
    monkeypatch.setattr(mod, "_load_plan_specs", AsyncMock(return_value={quota_id: spec}))
    monkeypatch.setattr(mod, "_acquire_once", AsyncMock(return_value=False))

    await mod.settle_provider_plan_from_callback(
        metadata={"gateway_provider_plan_id": str(plan_id)},
        status="success",
        cost_usd=Decimal("1"),
        total_tokens=100,
        request_id="dup",
    )

    guard.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_skips_bucket_upsert_without_request_id(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(quota_id=quota_id, label="24h", window_seconds=86400)

    guard = MagicMock()
    guard.commit = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_plan_guard", lambda: guard)
    monkeypatch.setattr(mod, "_load_plan_specs", AsyncMock(return_value={quota_id: spec}))
    schedule = MagicMock()
    monkeypatch.setattr(mod, "schedule_quota_plan_usage_upsert", schedule)

    await mod.settle_provider_plan_from_callback(
        metadata={"gateway_provider_plan_id": str(plan_id)},
        status="success",
        cost_usd=Decimal("1"),
        total_tokens=100,
        request_id=None,
    )

    guard.commit.assert_awaited_once()
    schedule.assert_not_called()
