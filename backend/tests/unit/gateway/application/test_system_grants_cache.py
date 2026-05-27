"""system_gateway_grants 本地缓存。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from domains.gateway.application.system_grants_cache import (
    clear_grants_cache_for_tests,
    get_cached_grant_keys,
    invalidate_grants_for_team,
    put_cached_grant_keys,
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    clear_grants_cache_for_tests()


@pytest.mark.asyncio
async def test_local_grants_cache_hit() -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    grant = SimpleNamespace(subject_kind="user", subject_id=user_id)
    await put_cached_grant_keys(team_id, user_id, [grant])  # type: ignore[list-item]
    hit = await get_cached_grant_keys(team_id, user_id)
    assert hit == frozenset({("user", user_id)})


@pytest.mark.asyncio
async def test_invalidate_grants_for_team() -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    grant = SimpleNamespace(subject_kind="user", subject_id=user_id)
    await put_cached_grant_keys(team_id, user_id, [grant])  # type: ignore[list-item]
    await invalidate_grants_for_team(team_id)
    assert await get_cached_grant_keys(team_id, user_id) is None
