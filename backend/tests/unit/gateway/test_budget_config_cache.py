"""budget_config_cache 单测。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application.budget_config_cache import (
    BudgetConfigRow,
    budget_config_coord_key,
    clear_budget_config_cache_for_tests,
    get_cached_budget_by_plan,
    invalidate_budget_config_cache,
)
from domains.gateway.domain.proxy_policy import BudgetCheckQuery


def test_budget_config_coord_key() -> None:
    row = BudgetConfigRow(
        target_kind="tenant",
        target_id=uuid.uuid4(),
        period="monthly",
        model_name=None,
        limit_usd=Decimal("100"),
        limit_tokens=None,
        limit_requests=None,
    )
    assert budget_config_coord_key(row) == (
        row.target_kind,
        row.target_id,
        row.period,
        row.model_name,
    )


@pytest.mark.asyncio
async def test_get_cached_budget_by_plan_hits_local_cache(monkeypatch) -> None:
    clear_budget_config_cache_for_tests()
    calls = 0
    tid = uuid.uuid4()
    plan = (BudgetCheckQuery("tenant", tid, "daily", None),)

    async def loader() -> dict:
        nonlocal calls
        calls += 1
        orm_row = SimpleNamespace(
            target_kind="tenant",
            target_id=tid,
            period="daily",
            model_name=None,
            limit_usd=Decimal("5"),
            limit_tokens=None,
            limit_requests=None,
        )
        return {("tenant", tid, "daily", None): orm_row}

    monkeypatch.setattr(
        "domains.gateway.application.budget_config_cache._get_version",
        AsyncMock(return_value="7"),
    )
    monkeypatch.setattr(
        "domains.gateway.application.budget_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )

    first = await get_cached_budget_by_plan(plan, loader)
    second = await get_cached_budget_by_plan(plan, loader)

    assert calls == 1
    assert first == second
    assert first[("tenant", tid, "daily", None)].limit_usd == Decimal("5")


@pytest.mark.asyncio
async def test_invalidate_budget_config_cache_clears_local(monkeypatch) -> None:
    clear_budget_config_cache_for_tests()
    calls = 0
    tid = uuid.uuid4()
    plan = (BudgetCheckQuery("tenant", tid, "daily", None),)

    async def loader() -> dict:
        nonlocal calls
        calls += 1
        orm_row = SimpleNamespace(
            target_kind="tenant",
            target_id=tid,
            period="daily",
            model_name=None,
            limit_usd=Decimal("1"),
            limit_tokens=None,
            limit_requests=None,
        )
        return {("tenant", tid, "daily", None): orm_row}

    version = {"v": "1"}

    async def fake_version() -> str:
        return version["v"]

    monkeypatch.setattr(
        "domains.gateway.application.budget_config_cache._get_version",
        fake_version,
    )
    monkeypatch.setattr(
        "domains.gateway.application.budget_config_cache._get_redis_client",
        AsyncMock(return_value=None),
    )
    redis_client = AsyncMock()
    monkeypatch.setattr(
        "domains.gateway.application.budget_config_cache._get_redis_client",
        AsyncMock(return_value=redis_client),
    )

    await get_cached_budget_by_plan(plan, loader)
    assert calls == 1

    version["v"] = "2"
    await invalidate_budget_config_cache()
    redis_client.incr.assert_awaited_once()

    await get_cached_budget_by_plan(plan, loader)
    assert calls == 2
