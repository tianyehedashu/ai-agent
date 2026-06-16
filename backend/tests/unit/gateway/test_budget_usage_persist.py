"""budget_usage_persist 幂等单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application import budget_usage_persist as mod
from domains.gateway.domain.quota_plan import PLATFORM_NS


@pytest.mark.asyncio
async def test_bucket_upsert_skipped_when_idempotency_key_exists(monkeypatch) -> None:
    budget_id = uuid.uuid4()
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", AsyncMock(return_value=False))
    increment = AsyncMock()
    monkeypatch.setattr(
        mod.QuotaPlanUsageBucketRepository,
        "increment_bucket",
        increment,
    )

    await mod._upsert_platform_budget_usage(
        items=[mod.PlatformBudgetUpsertItem(budget_id=budget_id, period="daily")],
        delta_tokens=100,
        delta_cost_usd=Decimal("0.01"),
        delta_requests=1,
        request_id="req-dup",
        source="proxy",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    increment.assert_not_called()


@pytest.mark.asyncio
async def test_bucket_upsert_releases_idempotency_key_on_failure(monkeypatch) -> None:
    budget_id = uuid.uuid4()
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

    await mod._upsert_platform_budget_usage(
        items=[mod.PlatformBudgetUpsertItem(budget_id=budget_id, period="daily")],
        delta_tokens=1,
        delta_cost_usd=Decimal("0"),
        delta_requests=1,
        request_id="req-fail",
        source="proxy",
        settled_at=datetime(2026, 6, 20, 12, 0, tzinfo=UTC),
    )

    release.assert_awaited_once_with(PLATFORM_NS, "req-fail", "proxy")


def test_schedule_skipped_without_request_id(monkeypatch) -> None:
    create_task = MagicMock()
    monkeypatch.setattr(mod.asyncio, "create_task", create_task)
    mod.schedule_platform_budget_usage_upsert(
        items=[mod.PlatformBudgetUpsertItem(budget_id=uuid.uuid4(), period="daily")],
        delta_tokens=1,
        delta_cost_usd=Decimal("0"),
        request_id=None,
    )
    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_registers_deferred_task(monkeypatch) -> None:
    registered: list[object] = []
    monkeypatch.setattr(mod, "register_proxy_deferred_task", lambda t: registered.append(t))
    monkeypatch.setattr(mod.asyncio, "create_task", lambda coro: MagicMock())

    mod.schedule_platform_budget_usage_upsert(
        items=[mod.PlatformBudgetUpsertItem(budget_id=uuid.uuid4(), period="daily")],
        delta_tokens=10,
        delta_cost_usd=Decimal("0"),
        request_id="req-1",
    )
    assert len(registered) == 1


@pytest.mark.asyncio
async def test_proxy_and_callback_sources_both_allowed(monkeypatch) -> None:
    acquire = AsyncMock(side_effect=[True, True])
    monkeypatch.setattr(mod, "_acquire_bucket_upsert_once", acquire)
    monkeypatch.setattr(
        mod,
        "get_session_context",
        lambda: _DummySessionCM(),
    )

    class _Repo:
        def __init__(self, _session: object) -> None:
            pass

        async def increment_bucket(self, *args: object, **kwargs: object) -> None:
            return None

    monkeypatch.setattr(mod, "QuotaPlanUsageBucketRepository", _Repo)
    budget_id = uuid.uuid4()
    item = mod.PlatformBudgetUpsertItem(budget_id=budget_id, period="daily")
    settled = datetime(2026, 6, 20, 12, 0, tzinfo=UTC)

    await mod._upsert_platform_budget_usage(
        items=[item],
        delta_tokens=50,
        delta_cost_usd=Decimal("0"),
        delta_requests=1,
        request_id="req-defer",
        source="proxy",
        settled_at=settled,
    )
    await mod._upsert_platform_budget_usage(
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


class _DummySessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> None:
        return None
