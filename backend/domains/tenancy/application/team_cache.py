"""Team / TeamMember 读路径短 TTL 进程内缓存。"""

from __future__ import annotations

from dataclasses import dataclass
import time
from uuid import UUID

from domains.tenancy.infrastructure.models.team import Team

_TTL_SEC = 60.0
_MAX_ENTRIES = 2048

_team_cache: dict[UUID, tuple[CachedTeamSnapshot | None, float]] = {}
_member_role_cache: dict[tuple[UUID, UUID], tuple[str | None, float]] = {}

CACHE_MISS = object()


@dataclass(frozen=True, slots=True)
class CachedTeamSnapshot:
    """Team 读路径快照（仅缓存展示/归属字段，避免跨请求 ORM 实例）。"""

    id: UUID
    kind: str
    name: str
    owner_user_id: UUID
    slug: str


def snapshot_from_team(team: Team | None) -> CachedTeamSnapshot | None:
    if team is None:
        return None
    return CachedTeamSnapshot(
        id=team.id,
        kind=team.kind,
        name=team.name,
        owner_user_id=team.owner_user_id,
        slug=team.slug,
    )


def team_from_snapshot(snapshot: CachedTeamSnapshot) -> Team:
    """构造 detached ``Team`` 供只读字段访问（不绑定 session）。"""
    return Team(
        id=snapshot.id,
        name=snapshot.name,
        slug=snapshot.slug,
        kind=snapshot.kind,
        owner_user_id=snapshot.owner_user_id,
        settings=None,
        is_active=True,
    )


def peek_cached_team_snapshot(team_id: UUID) -> CachedTeamSnapshot | None | object:
    hit = _team_cache.get(team_id)
    if hit is None:
        return CACHE_MISS
    snapshot, ts = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _team_cache.pop(team_id, None)
        return CACHE_MISS
    return snapshot


def put_cached_team_snapshot(team_id: UUID, team: Team | None) -> None:
    if len(_team_cache) >= _MAX_ENTRIES:
        _evict_oldest(_team_cache)
    _team_cache[team_id] = (snapshot_from_team(team), time.monotonic())


def peek_cached_member_role(team_id: UUID, user_id: UUID) -> str | None | object:
    key = (team_id, user_id)
    hit = _member_role_cache.get(key)
    if hit is None:
        return CACHE_MISS
    role, ts = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _member_role_cache.pop(key, None)
        return CACHE_MISS
    return role


def put_cached_member_role(team_id: UUID, user_id: UUID, role: str | None) -> None:
    if len(_member_role_cache) >= _MAX_ENTRIES:
        _evict_oldest(_member_role_cache)
    _member_role_cache[(team_id, user_id)] = (role, time.monotonic())


def invalidate_team(team_id: UUID) -> None:
    _team_cache.pop(team_id, None)
    keys = [k for k in _member_role_cache if k[0] == team_id]
    for key in keys:
        _member_role_cache.pop(key, None)


def invalidate_member(team_id: UUID, user_id: UUID) -> None:
    _member_role_cache.pop((team_id, user_id), None)


def clear_team_cache_for_tests() -> None:
    _team_cache.clear()
    _member_role_cache.clear()


def _evict_oldest(cache: dict[object, tuple[object, float]]) -> None:
    if not cache:
        return
    oldest_key = min(cache.items(), key=lambda item: item[1][1])[0]
    cache.pop(oldest_key, None)


__all__ = [
    "CACHE_MISS",
    "CachedTeamSnapshot",
    "clear_team_cache_for_tests",
    "invalidate_member",
    "invalidate_team",
    "peek_cached_member_role",
    "peek_cached_team_snapshot",
    "put_cached_member_role",
    "put_cached_team_snapshot",
    "snapshot_from_team",
    "team_from_snapshot",
]
