"""resolve_model_or_route 进程内缓存。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.resolve_model_cache import (
    CACHE_MISS,
    clear_resolve_model_cache_for_tests,
    hydrate_resolve_cache_entry,
    invalidate_for_tenant,
    is_negative_resolve_cache,
    peek_resolve_cache_entry,
    put_resolve_cache_entry,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_resolve_model_cache_for_tests()


def test_negative_cache_round_trip() -> None:
    team_id = uuid.uuid4()
    put_resolve_cache_entry(team_id, "missing-model", user_id=None, resolved=None)
    hit = peek_resolve_cache_entry(team_id, "missing-model", user_id=None)
    assert hit is not CACHE_MISS
    assert is_negative_resolve_cache(hit)  # type: ignore[arg-type]


def test_positive_cache_stores_ids_not_orm() -> None:
    team_id = uuid.uuid4()
    record_id = uuid.uuid4()
    record = SimpleNamespace(id=record_id, provider="openai", real_model="gpt-4")
    resolved = ResolvedModelName(record=record, route=None, via_route=None)  # type: ignore[arg-type]
    put_resolve_cache_entry(team_id, "my-model", user_id=None, resolved=resolved)
    hit = peek_resolve_cache_entry(team_id, "my-model", user_id=None)
    assert hit is not CACHE_MISS
    assert not is_negative_resolve_cache(hit)  # type: ignore[arg-type]
    assert hit.record_id == record_id  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_hydrate_returns_none_for_negative_entry() -> None:
    from domains.gateway.application.resolve_model_cache import _NegativeResolveCacheEntry

    result = await hydrate_resolve_cache_entry(
        session=object(),  # type: ignore[arg-type]
        payload=_NegativeResolveCacheEntry(),
    )
    assert result is None


def test_invalidate_for_tenant() -> None:
    team_id = uuid.uuid4()
    other_team = uuid.uuid4()
    put_resolve_cache_entry(team_id, "a", user_id=None, resolved=None)
    put_resolve_cache_entry(other_team, "b", user_id=None, resolved=None)
    invalidate_for_tenant(team_id)
    assert peek_resolve_cache_entry(team_id, "a", user_id=None) is CACHE_MISS
    assert peek_resolve_cache_entry(other_team, "b", user_id=None) is not CACHE_MISS
