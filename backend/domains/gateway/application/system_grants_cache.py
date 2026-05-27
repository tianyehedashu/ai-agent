"""``system_gateway_grants`` 可见集 Redis 缓存（5min TTL）。"""

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

_TTL_SEC = 300.0
_LOCAL: dict[tuple[UUID, UUID | None], tuple[frozenset[tuple[str, UUID]], float]] = {}
_LOCAL_MAX = 1024
_REDIS_PREFIX = "gw:grants:"


def _redis_key(team_id: UUID, user_id: UUID | None) -> str:
    uid = str(user_id) if user_id is not None else "_"
    return f"{_REDIS_PREFIX}{team_id}:{uid}"


def _grants_to_keys(grants: list[SystemGatewayGrant]) -> frozenset[tuple[str, UUID]]:
    return frozenset((g.subject_kind, g.subject_id) for g in grants)


async def get_cached_grant_keys(
    team_id: UUID,
    user_id: UUID | None,
) -> frozenset[tuple[str, UUID]] | None:
    """命中返回 granted_keys；未命中返回 ``None``。"""
    local_hit = _get_local(team_id, user_id)
    if local_hit is not None:
        return local_hit
    redis = await _get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(_redis_key(team_id, user_id))
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
    _put_local(team_id, user_id, granted)
    return granted


async def put_cached_grant_keys(
    team_id: UUID,
    user_id: UUID | None,
    grants: list[SystemGatewayGrant],
) -> None:
    granted = _grants_to_keys(grants)
    _put_local(team_id, user_id, granted)
    redis = await _get_redis()
    if redis is None:
        return
    payload = json.dumps([[kind, str(uid)] for kind, uid in sorted(granted)])
    try:
        await redis.set(_redis_key(team_id, user_id), payload, ex=int(_TTL_SEC))
    except Exception:
        logger.warning("Redis grants cache write failed", exc_info=True)


async def invalidate_grants_for_team(team_id: UUID) -> None:
    keys = [k for k in _LOCAL if k[0] == team_id]
    for key in keys:
        _LOCAL.pop(key, None)
    redis = await _get_redis()
    if redis is None:
        return
    pattern = f"{_REDIS_PREFIX}{team_id}:*"
    try:
        async for key in redis.scan_iter(match=pattern, count=64):
            await redis.delete(key)
    except Exception:
        logger.warning("Redis grants cache invalidate failed", exc_info=True)


async def invalidate_all_grants_cache() -> None:
    _LOCAL.clear()
    redis = await _get_redis()
    if redis is None:
        return
    try:
        async for key in redis.scan_iter(match=f"{_REDIS_PREFIX}*", count=128):
            await redis.delete(key)
    except Exception:
        logger.warning("Redis grants cache full invalidate failed", exc_info=True)


def clear_grants_cache_for_tests() -> None:
    _LOCAL.clear()


def _get_local(team_id: UUID, user_id: UUID | None) -> frozenset[tuple[str, UUID]] | None:
    hit = _LOCAL.get((team_id, user_id))
    if hit is None:
        return None
    granted, ts = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _LOCAL.pop((team_id, user_id), None)
        return None
    return granted


def _put_local(
    team_id: UUID,
    user_id: UUID | None,
    granted: frozenset[tuple[str, UUID]],
) -> None:
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[(team_id, user_id)] = (granted, time.monotonic())


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
