"""``gateway_route_snapshot`` 元数据 Redis 版本号 + 进程内 L1 缓存。

跨进程一致性：写路径（路由启停/修改/删除）通过 :func:`invalidate_route_snapshot_cache_for_tenant`
bump Redis 版本号 ``gw:route_snapshot:ver:<tenant>``；所有 worker 读路径比较本地
版本号决定是否过期，避免单纯 TTL 在多 worker 下最长 60s 的旧值窗口。

降级：Redis 不可用时退化为单调时钟 TTL（行为与旧版一致）。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.domain.route.route_snapshot import build_route_snapshot_metadata
from domains.gateway.infrastructure.repositories.model_repository import GatewayRouteRepository
from utils.logging import get_logger

logger = get_logger(__name__)

_CACHE: dict[tuple[UUID, str], tuple[dict[str, Any] | None, float, str]] = {}
"""key → (payload, ts, version)。``version`` 为写入时该租户的 Redis 版本号。"""

_TTL_SEC = 60.0

# Redis 版本号 key 前缀
_REDIS_VERSION_KEY_PREFIX = "gw:route_snapshot:ver:"

# 本进程对 tenant_id → 最新已知版本号的 L1 限流缓存（避免每次读都打 Redis）
_TENANT_VERSION_L1: dict[UUID, str] = {}
_TENANT_VERSION_L1_TTL = 5.0
_TENANT_VERSION_TS: dict[UUID, float] = {}

# fire-and-forget task 强引用集合，避免被 GC；完成后自动 discard
_PENDING_BUMP_TASKS: set[Any] = set()


async def _fetch_tenant_version(team_id: UUID) -> str:
    """读取租户当前 Redis 版本号；带 5s L1 限流，失败/无 Redis 退化为空串。"""
    now = time.monotonic()
    ts = _TENANT_VERSION_TS.get(team_id, 0.0)
    cached = _TENANT_VERSION_L1.get(team_id)
    if cached is not None and now - ts < _TENANT_VERSION_L1_TTL:
        return cached
    try:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()
    except Exception:
        return cached or ""
    try:
        raw = await client.get(f"{_REDIS_VERSION_KEY_PREFIX}{team_id}")
        version = raw.decode() if isinstance(raw, bytes) else (raw or "0")
    except Exception:
        return cached or ""
    _TENANT_VERSION_L1[team_id] = version
    _TENANT_VERSION_TS[team_id] = now
    return version


async def get_route_snapshot_metadata(
    session: AsyncSession,
    team_id: UUID,
    virtual_model: str,
) -> dict[str, Any] | None:
    """若 ``virtual_model`` 命中已启用路由则返回快照 dict，否则 ``None``。负结果亦缓存。"""
    key = (team_id, virtual_model)
    now = time.monotonic()
    hit = _CACHE.get(key)
    if hit is not None:
        payload, ts, stored_version = hit
        if now - ts < _TTL_SEC:
            current_version = await _fetch_tenant_version(team_id)
            if current_version == stored_version:
                return payload
        # TTL 或版本号变化 → 失效，落库重查
        _CACHE.pop(key, None)
    route = await GatewayRouteRepository(session).resolve_by_virtual_model(team_id, virtual_model)
    if route is None:
        _CACHE[key] = (None, now, await _fetch_tenant_version(team_id))
        return None
    snap = build_route_snapshot_metadata(route)
    _CACHE[key] = (snap, now, await _fetch_tenant_version(team_id))
    return snap


def invalidate_route_snapshot_cache_for_tenant(tenant_id: UUID) -> None:
    """失效本进程 L1 + 异步 bump Redis 版本号，通知所有 worker。"""
    keys = [k for k in _CACHE if k[0] == tenant_id]
    for key in keys:
        _CACHE.pop(key, None)
    _TENANT_VERSION_L1.pop(tenant_id, None)
    _TENANT_VERSION_TS.pop(tenant_id, None)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    task = asyncio.create_task(_bump_redis_version(tenant_id))
    _PENDING_BUMP_TASKS.add(task)
    task.add_done_callback(_PENDING_BUMP_TASKS.discard)


async def _bump_redis_version(tenant_id: UUID) -> None:
    try:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()
        await client.incr(f"{_REDIS_VERSION_KEY_PREFIX}{tenant_id}")
    except Exception:
        logger.warning(
            "route_snapshot_cache version bump failed: tenant_id=%s", tenant_id, exc_info=True
        )


def clear_route_snapshot_cache_for_tests() -> None:
    """单测隔离：清空模块级缓存。"""
    _CACHE.clear()
    _TENANT_VERSION_L1.clear()
    _TENANT_VERSION_TS.clear()
    for task in list(_PENDING_BUMP_TASKS):
        task.cancel()
    _PENDING_BUMP_TASKS.clear()


__all__ = [
    "clear_route_snapshot_cache_for_tests",
    "get_route_snapshot_metadata",
    "invalidate_route_snapshot_cache_for_tenant",
]
