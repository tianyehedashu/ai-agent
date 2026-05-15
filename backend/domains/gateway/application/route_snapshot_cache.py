"""``gateway_route_snapshot`` 元数据短 TTL 缓存（降低 ``ProxyUseCase._build_metadata`` 热路径读库）。"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.repositories.model_repository import GatewayRouteRepository

_CACHE: dict[tuple[UUID, str], tuple[dict[str, Any] | None, float]] = {}
_TTL_SEC = 60.0


async def get_route_snapshot_metadata(
    session: AsyncSession,
    team_id: UUID,
    virtual_model: str,
) -> dict[str, Any] | None:
    """若 ``virtual_model`` 命中已启用路由则返回快照 dict，否则 ``None``。负结果亦缓存 TTL 秒。"""
    key = (team_id, virtual_model)
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit is not None:
        payload, ts = hit
        if now - ts < _TTL_SEC:
            return payload
    route = await GatewayRouteRepository(session).get_by_virtual_model(team_id, virtual_model)
    if route is None:
        _CACHE[key] = (None, now)
        return None
    snap: dict[str, Any] = {
        "virtual_model": route.virtual_model,
        "primary_models": list(route.primary_models or []),
        "strategy": route.strategy,
    }
    _CACHE[key] = (snap, now)
    return snap


def clear_route_snapshot_cache_for_tests() -> None:
    """单测隔离：清空模块级缓存。"""
    _CACHE.clear()


__all__ = ["clear_route_snapshot_cache_for_tests", "get_route_snapshot_metadata"]
