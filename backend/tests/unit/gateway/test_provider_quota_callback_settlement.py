"""ProviderQuota callback 结算单测。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application import provider_quota_callback_settlement as mod
from domains.gateway.domain.quota_plan import PlanQuotaSpec, QuotaPlanReservation


@pytest.mark.asyncio
async def test_commit_provider_quota_on_success(monkeypatch) -> None:
    rule_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=rule_id,
        label="24h",
        window_seconds=86400,
        limit_tokens=4_000_000,
    )

    guard = MagicMock()
    guard.commit_rule = AsyncMock()
    guard.release_rule = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_quota_guard", lambda: guard)
    monkeypatch.setattr(mod, "_load_rule_specs", AsyncMock(return_value={rule_id: spec}))
    monkeypatch.setattr(mod, "acquire_settlement_once", AsyncMock(return_value=True))
    schedule = AsyncMock()
    monkeypatch.setattr(mod, "schedule_quota_plan_usage_upsert", schedule)

    await mod.settle_provider_quota_from_callback(
        metadata={
            "gateway_provider_plan_id": str(rule_id),
            "gateway_provider_quota_reservations": [
                {"rule_id": str(rule_id), "quota_id": str(rule_id), "minute_unix": 1, "reserved_requests": 1},
            ],
        },
        status="success",
        cost_usd=Decimal("0"),
        total_tokens=12_345,
        request_id="req-1",
    )

    guard.commit_rule.assert_awaited_once_with(
        rule_id,
        spec,
        delta_tokens=12_345,
        delta_usd=Decimal("0"),
    )
    guard.release_rule.assert_not_awaited()
    schedule.assert_called_once()


@pytest.mark.asyncio
async def test_release_provider_quota_on_failure(monkeypatch) -> None:
    rule_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=rule_id,
        label="24h",
        window_seconds=86400,
        limit_tokens=4_000_000,
    )
    reservation = QuotaPlanReservation(
        plan_id=rule_id,
        spec=spec,
        minute_unix=1,
        reserved_requests=1,
    )

    guard = MagicMock()
    guard.commit_rule = AsyncMock()
    guard.release_rule = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_quota_guard", lambda: guard)
    monkeypatch.setattr(mod, "_load_rule_specs", AsyncMock(return_value={rule_id: spec}))
    monkeypatch.setattr(mod, "acquire_settlement_once", AsyncMock(return_value=True))

    await mod.settle_provider_quota_from_callback(
        metadata={
            "gateway_provider_plan_id": str(rule_id),
            "gateway_provider_quota_reservations": [
                {"rule_id": str(rule_id), "quota_id": str(rule_id), "minute_unix": 1, "reserved_requests": 1},
            ],
        },
        status="failed",
        cost_usd=Decimal("0"),
        total_tokens=0,
        request_id="req-2",
    )

    guard.commit_rule.assert_not_awaited()
    guard.release_rule.assert_awaited_once()
    released = guard.release_rule.await_args.args[0]
    assert released.rule_id == rule_id
    assert released.reservation.minute_unix == reservation.minute_unix


@pytest.mark.asyncio
async def test_settle_noop_without_metadata(monkeypatch) -> None:
    guard = MagicMock()
    guard.commit_rule = AsyncMock()
    guard.release_rule = AsyncMock()
    monkeypatch.setattr(mod, "get_provider_quota_guard", lambda: guard)

    await mod.settle_provider_quota_from_callback(
        metadata={},
        status="success",
        cost_usd=Decimal("1"),
        total_tokens=100,
        request_id="req-3",
    )

    guard.commit_rule.assert_not_awaited()
    guard.release_rule.assert_not_awaited()
