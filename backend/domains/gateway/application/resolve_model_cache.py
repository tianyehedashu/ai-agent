"""``resolve_model_or_route`` 进程内 LRU + TTL 缓存（仅存 id 指针，回表再 hydrate）。"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Literal
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.model_or_route_resolution import ResolvedModelName

_CACHE: dict[tuple[UUID, UUID | None, str], tuple[_ResolveCachePayload, float]] = {}
_TTL_SEC = 60.0
_MAX_ENTRIES = 4096

CACHE_MISS = object()


@dataclass(frozen=True, slots=True)
class _NegativeResolveCacheEntry:
    """负缓存：该 model 名在此 tenant/user 下不可解析。"""


@dataclass(frozen=True, slots=True)
class _PositiveResolveCacheEntry:
    record_id: UUID
    record_kind: Literal["tenant", "system"]
    route_id: UUID | None
    via_route: str | None


_ResolveCachePayload = _NegativeResolveCacheEntry | _PositiveResolveCacheEntry


def _cache_key(team_id: UUID, name: str, *, user_id: UUID | None) -> tuple[UUID, UUID | None, str]:
    return (team_id, user_id, name.strip())


def peek_resolve_cache_entry(
    team_id: UUID,
    name: str,
    *,
    user_id: UUID | None,
) -> _ResolveCachePayload | None | object:
    """命中返回 payload；负/正缓存均可能；未命中返回 ``CACHE_MISS``。"""
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
        _CACHE[key] = (_NegativeResolveCacheEntry(), time.monotonic())
        return
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel

    record = resolved.record
    record_kind: Literal["tenant", "system"] = (
        "system" if isinstance(record, SystemGatewayModel) else "tenant"
    )
    route_id = resolved.route.id if resolved.route is not None else None
    _CACHE[key] = (
        _PositiveResolveCacheEntry(
            record_id=record.id,
            record_kind=record_kind,
            route_id=route_id,
            via_route=resolved.via_route,
        ),
        time.monotonic(),
    )


def is_negative_resolve_cache(payload: _ResolveCachePayload) -> bool:
    return isinstance(payload, _NegativeResolveCacheEntry)


async def hydrate_resolve_cache_entry(
    session: AsyncSession,
    payload: _ResolveCachePayload,
) -> ResolvedModelName | None:
    """把缓存指针还原为 ``ResolvedModelName``（1–2 次点查，避免 stale ORM）。"""
    from domains.gateway.application.model_or_route_resolution import ResolvedModelName
    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.system_gateway import (
        SystemGatewayModel,
        SystemGatewayRoute,
    )
    from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository

    if isinstance(payload, _NegativeResolveCacheEntry):
        return None

    repo = GatewayModelRepository(session)
    record: GatewayModel | SystemGatewayModel | None
    if payload.record_kind == "system":
        record = await repo.get_system(payload.record_id)
    else:
        record = await session.get(GatewayModel, payload.record_id)

    if record is None:
        return None

    route: GatewayRoute | SystemGatewayRoute | None = None
    if payload.route_id is not None:
        route = await session.get(GatewayRoute, payload.route_id)
        if route is None:
            route = await session.get(SystemGatewayRoute, payload.route_id)

    return ResolvedModelName(
        record=record,
        route=route,
        via_route=payload.via_route,
    )


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
    "hydrate_resolve_cache_entry",
    "invalidate_all",
    "invalidate_for_tenant",
    "is_negative_resolve_cache",
    "peek_resolve_cache_entry",
    "put_resolve_cache_entry",
]
