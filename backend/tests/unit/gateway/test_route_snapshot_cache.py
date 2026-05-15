"""``route_snapshot_cache`` TTL 与单测隔离。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

import domains.gateway.application.route_snapshot_cache as route_snapshot_cache_mod
from domains.gateway.application.route_snapshot_cache import (
    clear_route_snapshot_cache_for_tests,
    get_route_snapshot_metadata,
)


@pytest.fixture(autouse=True)
def _clear_route_snapshot_cache() -> None:
    clear_route_snapshot_cache_for_tests()
    yield
    clear_route_snapshot_cache_for_tests()


@pytest.mark.asyncio
async def test_get_route_snapshot_metadata_second_call_hits_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_mock = MagicMock()
    route_mock.virtual_model = "vm1"
    route_mock.primary_models = ["m1"]
    route_mock.strategy = "fallback"

    repo_instance = MagicMock()
    repo_instance.get_by_virtual_model = AsyncMock(return_value=route_mock)
    monkeypatch.setattr(
        route_snapshot_cache_mod,
        "GatewayRouteRepository",
        MagicMock(return_value=repo_instance),
    )

    team_id = uuid.uuid4()
    session = MagicMock()

    def mono() -> float:
        return 100.0

    monkeypatch.setattr(route_snapshot_cache_mod.time, "monotonic", mono)

    r1 = await get_route_snapshot_metadata(session, team_id, "vm1")
    r2 = await get_route_snapshot_metadata(session, team_id, "vm1")

    assert r1 == r2 == {
        "virtual_model": "vm1",
        "primary_models": ["m1"],
        "strategy": "fallback",
    }
    assert repo_instance.get_by_virtual_model.await_count == 1


@pytest.mark.asyncio
async def test_get_route_snapshot_metadata_refetches_after_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route_mock = MagicMock()
    route_mock.virtual_model = "vm1"
    route_mock.primary_models = []
    route_mock.strategy = "single"

    repo_instance = MagicMock()
    repo_instance.get_by_virtual_model = AsyncMock(return_value=route_mock)
    monkeypatch.setattr(
        route_snapshot_cache_mod,
        "GatewayRouteRepository",
        MagicMock(return_value=repo_instance),
    )

    team_id = uuid.uuid4()
    session = MagicMock()
    ticks: list[float] = [100.0, 170.0]

    def mono() -> float:
        return ticks.pop(0) if ticks else 999_999.0

    monkeypatch.setattr(route_snapshot_cache_mod.time, "monotonic", mono)

    await get_route_snapshot_metadata(session, team_id, "vm1")
    await get_route_snapshot_metadata(session, team_id, "vm1")

    assert repo_instance.get_by_virtual_model.await_count == 2


@pytest.mark.asyncio
async def test_clear_route_snapshot_cache_for_tests_clears_negative_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_instance = MagicMock()
    repo_instance.get_by_virtual_model = AsyncMock(return_value=None)
    monkeypatch.setattr(
        route_snapshot_cache_mod,
        "GatewayRouteRepository",
        MagicMock(return_value=repo_instance),
    )

    team_id = uuid.uuid4()
    session = MagicMock()
    monkeypatch.setattr(route_snapshot_cache_mod.time, "monotonic", MagicMock(return_value=0.0))

    await get_route_snapshot_metadata(session, team_id, "miss")
    clear_route_snapshot_cache_for_tests()
    await get_route_snapshot_metadata(session, team_id, "miss")

    assert repo_instance.get_by_virtual_model.await_count == 2
