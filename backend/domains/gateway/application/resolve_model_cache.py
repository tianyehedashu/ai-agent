"""``resolve_model_or_route`` 进程内 LRU + TTL 缓存。

正缓存保存 ``ResolvedModelName`` 的纯值快照，避免把 SQLAlchemy ORM 实例带出原 Session；
负缓存保存无解析结果标记。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from domains.gateway.application.model_or_route_resolution import ResolvedModelName

_NEGATIVE_ENTRY = object()  # 负缓存标记（无 resolve）
_CACHE: dict[tuple[UUID, UUID | None, str], tuple[object, float]] = {}
_TTL_SEC = 60.0
_MAX_ENTRIES = 4096

CACHE_MISS = object()


def _cache_key(team_id: UUID, name: str, *, user_id: UUID | None) -> tuple[UUID, UUID | None, str]:
    return (team_id, user_id, name.strip())


def peek_resolve_cache_entry(
    team_id: UUID,
    name: str,
    *,
    user_id: UUID | None,
) -> object:
    """命中返回缓存安全 ``ResolvedModelName``（正）/ ``None``（负）；未命中返回 ``CACHE_MISS``。"""
    cleaned = name.strip()
    if not cleaned:
        return None
    key = _cache_key(team_id, cleaned, user_id=user_id)
    hit = _CACHE.get(key)
    if hit is None:
        return CACHE_MISS
    payload, ts = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _CACHE.pop(key, None)
        return CACHE_MISS
    if payload is _NEGATIVE_ENTRY:
        return None
    return payload


def put_resolve_cache_entry(
    team_id: UUID,
    name: str,
    *,
    user_id: UUID | None,
    resolved: ResolvedModelName | None,
) -> None:
    cleaned = name.strip()
    if not cleaned:
        return
    if len(_CACHE) >= _MAX_ENTRIES:
        _evict_oldest()
    key = _cache_key(team_id, cleaned, user_id=user_id)
    if resolved is None:
        payload = _NEGATIVE_ENTRY
    else:
        from domains.gateway.application.model_or_route_resolution import (
            cache_safe_resolved_model_name,
        )

        payload = cache_safe_resolved_model_name(resolved)
    _CACHE[key] = (payload, time.monotonic())


def invalidate_for_tenant(tenant_id: UUID) -> None:
    keys = [k for k in _CACHE if k[0] == tenant_id]
    for key in keys:
        _CACHE.pop(key, None)


def invalidate_all() -> None:
    _CACHE.clear()


def clear_resolve_model_cache_for_tests() -> None:
    _CACHE.clear()


def _evict_oldest() -> None:
    if not _CACHE:
        return
    oldest_key = min(_CACHE.items(), key=lambda item: item[1][1])[0]
    _CACHE.pop(oldest_key, None)


__all__ = [
    "CACHE_MISS",
    "clear_resolve_model_cache_for_tests",
    "invalidate_all",
    "invalidate_for_tenant",
    "peek_resolve_cache_entry",
    "put_resolve_cache_entry",
]
