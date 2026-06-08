"""resolve_model_or_route 进程内缓存 (v2: 直接存 ResolvedModelName，无回表 hydrate)。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.resolve_model_cache import (
    CACHE_MISS,
    clear_resolve_model_cache_for_tests,
    invalidate_for_tenant,
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
    assert hit is None  # 负缓存返回 None（不再是 dataclass 包装）


def test_positive_cache_returns_resolved_object() -> None:
    team_id = uuid.uuid4()
    record = SimpleNamespace(id=uuid.uuid4(), provider="openai", real_model="gpt-4")
    resolved = ResolvedModelName(record=record, route=None, via_route=None)  # type: ignore[arg-type]
    put_resolve_cache_entry(team_id, "my-model", user_id=None, resolved=resolved)
    hit = peek_resolve_cache_entry(team_id, "my-model", user_id=None)
    assert hit is not CACHE_MISS
    assert hit is not None
    assert hit is resolved  # v2: 直接返回原始对象


def test_invalidate_for_tenant() -> None:
    team_id = uuid.uuid4()
    other_team = uuid.uuid4()
    put_resolve_cache_entry(team_id, "a", user_id=None, resolved=None)
    put_resolve_cache_entry(other_team, "b", user_id=None, resolved=None)
    invalidate_for_tenant(team_id)
    assert peek_resolve_cache_entry(team_id, "a", user_id=None) is CACHE_MISS
    assert peek_resolve_cache_entry(other_team, "b", user_id=None) is not CACHE_MISS
