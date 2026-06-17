"""quota_plan_usage_persist 幂等单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application import quota_plan_usage_persist as mod
from domains.gateway.domain.quota_plan import PROVIDER_NS, PlanQuotaSpec


@pytest.mark.asyncio
async def test_bucket_upsert_skipped_when_idempotency_key_exists(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="daily",
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        limit_tokens=1_000_000,
    )
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", AsyncMock(return_value=False))
    increment = AsyncMock()
    monkeypatch.setattr(
        mod.QuotaPlanUsageBucketRepository,
        "increment_bucket",
        increment,
    )

    await mod._upsert_quota_plan_usage(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        specs=[spec],
        delta_tokens=100,
        delta_cost_usd=Decimal("0"),
        delta_requests=1,
        request_id="req-dup",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    increment.assert_not_called()


@pytest.mark.asyncio
async def test_bucket_upsert_releases_idempotency_key_on_failure(monkeypatch) -> None:
    plan_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="daily",
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        limit_tokens=1_000_000,
    )
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", AsyncMock(return_value=True))
    release = AsyncMock()
    monkeypatch.setattr(mod, "_release_bucket_upsert_once", release)

    class _FailingRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def increment_bucket(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("db down")

    monkeypatch.setattr(mod, "QuotaPlanUsageBucketRepository", _FailingRepo)
    monkeypatch.setattr(
        mod,
        "get_session_context",
        lambda: _DummySessionCM(),
    )

    await mod._upsert_quota_plan_usage(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        specs=[spec],
        delta_tokens=1,
        delta_cost_usd=Decimal("0"),
        delta_requests=1,
        request_id="req-fail",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    release.assert_awaited_once_with(PROVIDER_NS, "req-fail")


@pytest.mark.asyncio
async def test_rolling_spec_skips_bucket_persist(monkeypatch) -> None:
    """滚动窗口不落 PG 桶：连幂等键都不应获取，increment 不调用。"""
    acquire = AsyncMock(return_value=True)
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", acquire)
    increment = AsyncMock()
    monkeypatch.setattr(mod.QuotaPlanUsageBucketRepository, "increment_bucket", increment)

    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="5h",
        window_seconds=18000,
        reset_strategy="rolling",
        limit_tokens=1_000_000,
    )
    await mod._upsert_quota_plan_usage(
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
    increment.assert_not_called()


def test_schedule_skipped_without_request_id(monkeypatch) -> None:
    create_task = MagicMock()
    monkeypatch.setattr(mod.asyncio, "create_task", create_task)
    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="daily",
        window_seconds=86400,
        limit_tokens=1,
    )
    mod.schedule_quota_plan_usage_upsert(
        ns=PROVIDER_NS,
        plan_id=uuid.uuid4(),
        specs=[spec],
        delta_tokens=1,
        delta_cost_usd=Decimal("0"),
        request_id=None,
    )
    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_registers_deferred_task(monkeypatch) -> None:
    registered: list[object] = []
    monkeypatch.setattr(mod, "register_proxy_deferred_task", lambda t: registered.append(t))
    monkeypatch.setattr(mod.asyncio, "create_task", lambda _coro: MagicMock())

    spec = PlanQuotaSpec(
        quota_id=uuid.uuid4(),
        label="daily",
        window_seconds=86400,
        limit_tokens=1_000_000,
    )
    mod.schedule_quota_plan_usage_upsert(
        ns=PROVIDER_NS,
        plan_id=uuid.uuid4(),
        specs=[spec],
        delta_tokens=10,
        delta_cost_usd=Decimal("0"),
        request_id="req-1",
    )
    assert len(registered) == 1


class _DummySessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None
