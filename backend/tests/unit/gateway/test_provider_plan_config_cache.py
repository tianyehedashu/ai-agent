"""provider_plan_config_cache 单测。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application.provider_plan_config_cache import (
    ProviderPlanConfigSnapshot,
    ProviderPlanQuotaConfigRow,
    clear_provider_plan_config_cache_for_tests,
    get_cached_active_provider_plan,
    invalidate_provider_plan_config_cache,
    plan_quota_specs_from_config,
)


def _snapshot(
    *,
    plan_id: uuid.UUID | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> ProviderPlanConfigSnapshot:
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    quota_id = uuid.uuid4()
    return ProviderPlanConfigSnapshot(
        plan_id=plan_id or uuid.uuid4(),
        valid_from=valid_from or (now - timedelta(days=1)),
        valid_until=valid_until or (now + timedelta(days=1)),
        quotas=(
            ProviderPlanQuotaConfigRow(
                quota_id=quota_id,
                label="daily",
                window_seconds=86400,
                reset_strategy="rolling",
                limit_usd=None,
                limit_tokens=None,
                limit_requests=100,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_get_cached_active_provider_plan_hits_local_cache(monkeypatch) -> None:
    clear_provider_plan_config_cache_for_tests()
    calls = 0
    cred_id = uuid.uuid4()
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    snap = _snapshot()

    async def loader() -> ProviderPlanConfigSnapshot | None:
        nonlocal calls
        calls += 1
        return snap

    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_version",
        AsyncMock(return_value="3"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )

    first = await get_cached_active_provider_plan(cred_id, "gpt-4o-mini", now=now, loader=loader)
    second = await get_cached_active_provider_plan(cred_id, "gpt-4o-mini", now=now, loader=loader)

    assert calls == 1
    assert first == snap
    assert second == snap
    specs = plan_quota_specs_from_config(snap)
    assert specs[0].limit_requests == 100


@pytest.mark.asyncio
async def test_no_active_plan_is_negatively_cached(monkeypatch) -> None:
    clear_provider_plan_config_cache_for_tests()
    calls = 0
    cred_id = uuid.uuid4()
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

    async def loader() -> ProviderPlanConfigSnapshot | None:
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_version",
        AsyncMock(return_value="5"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )

    first = await get_cached_active_provider_plan(cred_id, None, now=now, loader=loader)
    second = await get_cached_active_provider_plan(cred_id, None, now=now, loader=loader)

    assert calls == 1
    assert first is None
    assert second is None


@pytest.mark.asyncio
async def test_expired_plan_snapshot_is_not_returned(monkeypatch) -> None:
    clear_provider_plan_config_cache_for_tests()
    calls = 0
    cred_id = uuid.uuid4()
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    expired = _snapshot(
        valid_from=now - timedelta(days=10),
        valid_until=now - timedelta(days=1),
    )

    async def loader() -> ProviderPlanConfigSnapshot | None:
        nonlocal calls
        calls += 1
        return expired

    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_version",
        AsyncMock(return_value="6"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )

    result = await get_cached_active_provider_plan(cred_id, "m", now=now, loader=loader)
    assert result is None
    assert calls == 1


@pytest.mark.asyncio
async def test_invalidate_provider_plan_config_cache_clears_local(monkeypatch) -> None:
    clear_provider_plan_config_cache_for_tests()
    calls = 0
    cred_id = uuid.uuid4()
    now = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    snap = _snapshot()

    async def loader() -> ProviderPlanConfigSnapshot | None:
        nonlocal calls
        calls += 1
        return snap

    version = {"v": "1"}

    async def fake_version() -> str:
        return version["v"]

    redis_client = AsyncMock()
    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_version",
        fake_version,
    )
    monkeypatch.setattr(
        "domains.gateway.application.provider_plan_config_cache._get_redis_client",
        AsyncMock(return_value=redis_client),
    )

    await get_cached_active_provider_plan(cred_id, "m", now=now, loader=loader)
    assert calls == 1

    version["v"] = "2"
    await invalidate_provider_plan_config_cache()
    redis_client.incr.assert_awaited_once()

    await get_cached_active_provider_plan(cred_id, "m", now=now, loader=loader)
    assert calls == 2
