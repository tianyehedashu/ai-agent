"""``system_gateway_grants`` 可见集 Redis + 进程内 L1 缓存（版本号失效）。

跨进程一致性：写路径（grant 启停/删除/创建）通过 :func:`invalidate_grants_for_team`
bump Redis 版本号 ``gw:sysgrants:ver:<team>``，并删除 Redis 数据缓存条目；所有
worker 读路径比较本地版本号决定是否过期，避免单纯 TTL 在多 worker 下最长 5min
的旧值窗口。

降级：Redis 不可用时退化为单调时钟 TTL（行为与旧版一致）。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from uuid import UUID

from bootstrap.config import settings
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayGrant

logger = get_logger(__name__)

_TTL_SEC = 300.0  # 退化的兜底 TTL；正常情况下版本号变化立即失效
_LOCAL: dict[tuple[UUID, UUID | None], tuple[frozenset[tuple[str, UUID]], float, str]] = {}
"""(team_id, user_id) → (granted_keys, ts, version)。``version`` 为写入时版本号。"""
_LOCAL_MAX = 1024
_REDIS_PREFIX = "gw:grants:"
_REDIS_VERSION_KEY_PREFIX = "gw:sysgrants:ver:"

# 本进程对 tenant_id → 最新已知版本号的 L1 限流缓存（避免每次读都打 Redis）
_TENANT_VERSION_L1: dict[UUID, str] = {}
_TENANT_VERSION_L1_TTL = 5.0
_TENANT_VERSION_TS: dict[UUID, float] = {}


def _redis_key(team_id: UUID, user_id: UUID | None, *, version: str) -> str:
    uid = str(user_id) if user_id is not None else "_"
    return f"{_REDIS_PREFIX}{team_id}:{uid}:v:{version}"


def _grants_to_keys(grants: list[SystemGatewayGrant]) -> frozenset[tuple[str, UUID]]:
    return frozenset((g.subject_kind, g.subject_id) for g in grants)


async def _fetch_tenant_version(team_id: UUID) -> str:
    """读取租户当前 Redis 版本号；带 5s L1 限流，失败/无 Redis 退化为空串。"""
    now = time.monotonic()
    ts = _TENANT_VERSION_TS.get(team_id, 0.0)
    cached = _TENANT_VERSION_L1.get(team_id)
    if cached is not None and now - ts < _TENANT_VERSION_L1_TTL:
        return cached
    redis = await _get_redis()
    if redis is None:
        return cached or ""
    try:
        raw = await redis.get(f"{_REDIS_VERSION_KEY_PREFIX}{team_id}")
        version = raw.decode() if isinstance(raw, bytes) else (raw or "0")
    except Exception:
        logger.warning("Redis grants version read failed", exc_info=True)
        return cached or ""
    _TENANT_VERSION_L1[team_id] = version
    _TENANT_VERSION_TS[team_id] = now
    return version


async def get_cached_grant_keys(
    team_id: UUID,
    user_id: UUID | None,
) -> frozenset[tuple[str, UUID]] | None:
    """命中返回 granted_keys；未命中返回 ``None``。"""
    # 先拉版本号，再用版本号比对本地 L1
    version = await _fetch_tenant_version(team_id)
    local_hit = _get_local(team_id, user_id, current_version=version)
    if local_hit is not None:
        return local_hit
    redis = await _get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(_redis_key(team_id, user_id, version=version))
    except Exception:
        logger.warning("Redis grants cache read failed", exc_info=True)
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        keys = frozenset((str(k[0]), UUID(str(k[1]))) for k in payload)
        granted = frozenset((kind, uid) for kind, uid in keys)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    _put_local(team_id, user_id, granted, version)
    return granted


async def put_cached_grant_keys(
    team_id: UUID,
    user_id: UUID | None,
    grants: list[SystemGatewayGrant],
) -> None:
    granted = _grants_to_keys(grants)
    version = await _fetch_tenant_version(team_id)
    _put_local(team_id, user_id, granted, version)
    redis = await _get_redis()
    if redis is None:
        return
    payload = json.dumps([[kind, str(uid)] for kind, uid in sorted(granted)])
    try:
        # 按版本号写入数据条目；写路径 INCR 版本号后旧版本条目自然失效
        await redis.set(_redis_key(team_id, user_id, version=version), payload, ex=int(_TTL_SEC))
    except Exception:
        logger.warning("Redis grants cache write failed", exc_info=True)


async def invalidate_grants_for_team(team_id: UUID) -> None:
    """失效本进程 L1 + bump Redis 版本号 + 删除旧 Redis 数据条目。"""
    keys = [k for k in _LOCAL if k[0] == team_id]
    for key in keys:
        _LOCAL.pop(key, None)
    _TENANT_VERSION_L1.pop(team_id, None)
    _TENANT_VERSION_TS.pop(team_id, None)
    redis = await _get_redis()
    if redis is None:
        return
    try:
        # 先删除该 team 的所有版本数据条目，再 bump 版本号，确保读到旧版本的
        # worker 在 bump 后无法再命中旧条目
        async for key in redis.scan_iter(match=f"{_REDIS_PREFIX}{team_id}:*:v:*", count=128):
            await redis.delete(key)
        await redis.incr(f"{_REDIS_VERSION_KEY_PREFIX}{team_id}")
    except Exception:
        logger.warning("Redis grants cache invalidate failed", exc_info=True)


async def invalidate_all_grants_cache() -> None:
    _LOCAL.clear()
    _TENANT_VERSION_L1.clear()
    _TENANT_VERSION_TS.clear()
    redis = await _get_redis()
    if redis is None:
        return
    try:
        async for key in redis.scan_iter(match=f"{_REDIS_PREFIX}*:v:*", count=128):
            await redis.delete(key)
        async for key in redis.scan_iter(match=f"{_REDIS_VERSION_KEY_PREFIX}*", count=128):
            await redis.delete(key)
    except Exception:
        logger.warning("Redis grants cache full invalidate failed", exc_info=True)


def clear_grants_cache_for_tests() -> None:
    _LOCAL.clear()
    _TENANT_VERSION_L1.clear()
    _TENANT_VERSION_TS.clear()


def _get_local(
    team_id: UUID,
    user_id: UUID | None,
    *,
    current_version: str,
) -> frozenset[tuple[str, UUID]] | None:
    """本地 L1 命中检查：TTL 兜底 + 版本号比对。

    调用方 :func:`get_cached_grant_keys` 已拉取当前 Redis 版本号传入；若与本地
    stored_version 不一致则视为过期，跳过本地命中、重新拉 Redis。
    """
    hit = _LOCAL.get((team_id, user_id))
    if hit is None:
        return None
    granted, ts, stored_version = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _LOCAL.pop((team_id, user_id), None)
        return None
    if current_version != stored_version:
        # 版本号变化：本进程 L1 已过期，丢弃并触发回源
        _LOCAL.pop((team_id, user_id), None)
        return None
    return granted


def _put_local(
    team_id: UUID,
    user_id: UUID | None,
    granted: frozenset[tuple[str, UUID]],
    version: str,
) -> None:
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[(team_id, user_id)] = (granted, time.monotonic(), version)


async def _get_redis():
    url = settings.gateway_router_redis_url or settings.redis_url
    if not url:
        return None
    try:
        from libs.db.redis import get_redis_client

        return await get_redis_client()
    except Exception:
        return None


__all__ = [
    "clear_grants_cache_for_tests",
    "get_cached_grant_keys",
    "invalidate_all_grants_cache",
    "invalidate_grants_for_team",
    "put_cached_grant_keys",
]
