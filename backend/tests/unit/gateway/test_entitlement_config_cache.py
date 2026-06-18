"""entitlement_config_cache 单测：缓存命中/失效 + 纯过滤辅助。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application.entitlement_config_cache import (
    EntitlementPlanConfigRow,
    EntitlementQuotaConfigRow,
    _decode_rows,
    _encode_rows,
    clear_entitlement_config_cache_for_tests,
    enforceable_quotas,
    entitlement_plan_rows_from_orm,
    get_cached_entitlement_plans,
    invalidate_entitlement_config_cache,
    select_active_plan_config,
)


def _quota(**kw) -> EntitlementQuotaConfigRow:
    base = {
        "quota_id": uuid.uuid4(),
        "label": "default",
        "window_seconds": 86400,
        "reset_strategy": "rolling",
        "limit_usd": Decimal("10"),
        "limit_tokens": None,
        "limit_requests": None,
        "unit_price_usd_per_token": None,
        "unit_price_usd_per_request": None,
    }
    base.update(kw)
    return EntitlementQuotaConfigRow(**base)


def _plan(**kw) -> EntitlementPlanConfigRow:
    base = {
        "plan_id": uuid.uuid4(),
        "label": "p",
        "included_models": (),
        "included_capabilities": (),
        "quotas": (_quota(),),
    }
    base.update(kw)
    return EntitlementPlanConfigRow(**base)


def test_select_active_plan_config_filters_models_and_capabilities() -> None:
    gpt = _plan(label="gpt-only", included_models=("gpt-4o",))
    img = _plan(label="img-only", included_capabilities=("image",))
    rows = (gpt, img)

    assert select_active_plan_config(rows, virtual_model="gpt-4o", capability=None) is gpt
    # virtual_model 不在白名单 → 跳过 gpt，img 无 model 限制但 capability 不匹配 → None
    assert select_active_plan_config(rows, virtual_model="claude", capability=None) is img
    assert (
        select_active_plan_config(rows, virtual_model="claude", capability="image") is img
    )
    assert (
        select_active_plan_config((gpt,), virtual_model="claude", capability=None) is None
    )


def test_select_active_plan_config_returns_first_match() -> None:
    a = _plan(label="a")
    b = _plan(label="b")
    assert select_active_plan_config((a, b), virtual_model=None, capability=None) is a


def test_enforceable_quotas_drops_disabled_and_expired() -> None:
    now = datetime(2026, 6, 18, tzinfo=UTC)
    ok = _quota(label="ok")
    disabled = _quota(label="off", enabled=False)
    expired = _quota(label="old", valid_until=now - timedelta(days=1))
    plan = _plan(quotas=(ok, disabled, expired))
    result = enforceable_quotas(plan, now=now)
    assert [q.label for q in result] == ["ok"]


def test_entitlement_plan_rows_from_orm_orders_by_created_at_desc() -> None:
    older = SimpleNamespace(
        id=uuid.uuid4(),
        label="older",
        included_models=["gpt-4o"],
        included_capabilities=[],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer = SimpleNamespace(
        id=uuid.uuid4(),
        label="newer",
        included_models=[],
        included_capabilities=[],
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    quota = SimpleNamespace(
        id=uuid.uuid4(),
        label="default",
        window_seconds=3600,
        reset_strategy="rolling",
        reset_timezone="UTC",
        reset_time_minutes=0,
        reset_day_of_month=1,
        limit_usd=Decimal("1"),
        limit_tokens=None,
        limit_requests=None,
        unit_price_usd_per_token=None,
        unit_price_usd_per_request=None,
        enabled=True,
        valid_from=None,
        valid_until=None,
    )
    rows = entitlement_plan_rows_from_orm([(older, [quota]), (newer, [])])
    assert [r.label for r in rows] == ["newer", "older"]
    assert rows[1].included_models == ("gpt-4o",)
    assert len(rows[1].quotas) == 1


def test_encode_decode_roundtrip() -> None:
    plan = _plan(
        included_models=("gpt-4o",),
        included_capabilities=("text",),
        quotas=(
            _quota(
                limit_usd=Decimal("12.5"),
                unit_price_usd_per_token=Decimal("0.0001"),
                valid_from=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ),
    )
    decoded = _decode_rows(_encode_rows((plan,)))
    assert decoded[0].plan_id == plan.plan_id
    assert decoded[0].included_models == ("gpt-4o",)
    q = decoded[0].quotas[0]
    assert q.limit_usd == Decimal("12.5")
    assert q.unit_price_usd_per_token == Decimal("0.0001")
    assert q.valid_from == datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_get_cached_entitlement_plans_hits_local(monkeypatch) -> None:
    clear_entitlement_config_cache_for_tests()
    scope_id = uuid.uuid4()
    calls = 0

    async def loader() -> tuple[EntitlementPlanConfigRow, ...]:
        nonlocal calls
        calls += 1
        return (_plan(),)

    monkeypatch.setattr(
        "domains.gateway.application.entitlement_config_cache._get_version",
        AsyncMock(return_value="3"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.entitlement_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )

    first = await get_cached_entitlement_plans("vkey", scope_id, loader=loader)
    second = await get_cached_entitlement_plans("vkey", scope_id, loader=loader)
    assert calls == 1
    assert first == second


@pytest.mark.asyncio
async def test_empty_scope_is_negatively_cached(monkeypatch) -> None:
    clear_entitlement_config_cache_for_tests()
    scope_id = uuid.uuid4()
    calls = 0

    async def loader() -> tuple[EntitlementPlanConfigRow, ...]:
        nonlocal calls
        calls += 1
        return ()

    monkeypatch.setattr(
        "domains.gateway.application.entitlement_config_cache._get_version",
        AsyncMock(return_value="4"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.entitlement_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )

    await get_cached_entitlement_plans("vkey", scope_id, loader=loader)
    await get_cached_entitlement_plans("vkey", scope_id, loader=loader)
    assert calls == 1


@pytest.mark.asyncio
async def test_invalidate_bumps_version_and_reloads(monkeypatch) -> None:
    clear_entitlement_config_cache_for_tests()
    scope_id = uuid.uuid4()
    calls = 0
    version = {"v": "1"}

    async def loader() -> tuple[EntitlementPlanConfigRow, ...]:
        nonlocal calls
        calls += 1
        return (_plan(),)

    async def fake_version() -> str:
        return version["v"]

    redis_client = AsyncMock()
    monkeypatch.setattr(
        "domains.gateway.application.entitlement_config_cache._get_version",
        fake_version,
    )
    monkeypatch.setattr(
        "domains.gateway.application.entitlement_config_cache._get_redis_client",
        AsyncMock(return_value=redis_client),
    )

    await get_cached_entitlement_plans("vkey", scope_id, loader=loader)
    assert calls == 1

    version["v"] = "2"
    await invalidate_entitlement_config_cache()
    redis_client.incr.assert_awaited_once()

    await get_cached_entitlement_plans("vkey", scope_id, loader=loader)
    assert calls == 2
