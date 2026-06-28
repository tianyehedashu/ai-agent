"""gateway_resource_grants 可见集 Redis + 进程内 L1 缓存（版本号失效）。

跨进程一致性：写路径（grant 启停/删除/创建）通过 :func:`invalidate_resource_grants_for_team`
bump Redis 版本号 ``gw:resgrants:ver:<team>``，并删除 Redis 数据缓存条目；所有 worker
读路径比较本地版本号决定是否过期，避免单纯 TTL 在多 worker 下最长 5min 的旧值窗口。

降级：Redis 不可用时退化为单调时钟 TTL（行为与旧版一致）。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import TYPE_CHECKING
from uuid import UUID

from bootstrap.config import settings
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.resource_grant import GatewayResourceGrant

logger = get_logger(__name__)

_TTL_SEC = 300.0  # 退化的兜底 TTL；正常情况下版本号变化立即失效
_LOCAL_MAX = 1024
_REDIS_PREFIX = "gw:resgrants:"
_REDIS_VERSION_KEY_PREFIX = "gw:resgrants:ver:"


@dataclass(frozen=True, slots=True)
class ResourceGrantCacheEntry:
    """目标团队收到的 enabled grant 快照。"""

    granted_keys: frozenset[tuple[str, UUID]]
    owner_personal_slugs: frozenset[tuple[UUID, UUID, str]]
    """(owner_user_id, personal_team_id, slug) 去重列表，供 slug 消歧。"""


_LOCAL: dict[UUID, tuple[ResourceGrantCacheEntry, float, str]] = {}
"""team_id → (entry, ts, version)。``version`` 为写入时该租户的 Redis 版本号。"""


def _entry_from_grants(
    grants: list[GatewayResourceGrant],
    *,
    slug_rows: list[tuple[UUID, UUID, str]],
) -> ResourceGrantCacheEntry:
    keys = frozenset((g.subject_kind, g.subject_id) for g in grants if g.enabled)
    slugs = frozenset(slug_rows)
    return ResourceGrantCacheEntry(granted_keys=keys, owner_personal_slugs=slugs)


def build_slug_to_personal_team_map(
    entry: ResourceGrantCacheEntry,
) -> dict[str, UUID]:
    """slug → owner personal team_id（homonym slug 排除）。"""
    slug_counts: dict[str, int] = {}
    for _owner, _team, slug in entry.owner_personal_slugs:
        slug_counts[slug] = slug_counts.get(slug, 0) + 1
    out: dict[str, UUID] = {}
    for _owner, team_id, slug in entry.owner_personal_slugs:
        if slug_counts.get(slug, 0) == 1:
            out[slug] = team_id
    return out


async def _fetch_tenant_version(team_id: UUID) -> str:
    """读取租户当前 Redis 版本号；失败/无 Redis 退化为空串。"""
    try:
        redis = await _get_redis()
    except Exception:
        return ""
    if redis is None:
        return ""
    try:
        raw = await redis.get(f"{_REDIS_VERSION_KEY_PREFIX}{team_id}")
        return raw.decode() if isinstance(raw, bytes) else (raw or "0")
    except Exception:
        logger.warning("Redis resource grants version read failed", exc_info=True)
        return ""


async def get_cached_resource_grants(team_id: UUID) -> ResourceGrantCacheEntry | None:
    # 先拉版本号，再用版本号比对本地 L1
    version = await _fetch_tenant_version(team_id)
    local_hit = _get_local(team_id, current_version=version)
    if local_hit is not None:
        return local_hit
    redis = await _get_redis()
    if redis is None:
        return None
    # Redis 数据条目按版本号编排：仅当存在与当前版本号匹配的条目时才命中
    try:
        raw = await redis.get(f"{_REDIS_PREFIX}{team_id}:v:{version}")
    except Exception:
        logger.warning("Redis resource grants cache read failed", exc_info=True)
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
        keys = frozenset((str(k[0]), UUID(str(k[1]))) for k in payload.get("granted_keys", []))
        slugs = frozenset(
            (UUID(str(s[0])), UUID(str(s[1])), str(s[2])) for s in payload.get("owner_slugs", [])
        )
        entry = ResourceGrantCacheEntry(granted_keys=keys, owner_personal_slugs=slugs)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    _put_local(team_id, entry, version)
    return entry


async def put_cached_resource_grants(
    team_id: UUID,
    grants: list[GatewayResourceGrant],
    *,
    slug_rows: list[tuple[UUID, UUID, str]],
) -> ResourceGrantCacheEntry:
    entry = _entry_from_grants(grants, slug_rows=slug_rows)
    version = await _fetch_tenant_version(team_id)
    _put_local(team_id, entry, version)
    redis = await _get_redis()
    if redis is None:
        return entry
    payload = json.dumps(
        {
            "granted_keys": [[kind, str(uid)] for kind, uid in sorted(entry.granted_keys)],
            "owner_slugs": [
                [str(owner), str(team), slug]
                for owner, team, slug in sorted(entry.owner_personal_slugs)
            ],
        }
    )
    try:
        # 按版本号写入数据条目；写路径 INCR 版本号后旧版本条目自然失效
        await redis.set(f"{_REDIS_PREFIX}{team_id}:v:{version}", payload, ex=int(_TTL_SEC))
    except Exception:
        logger.warning("Redis resource grants cache write failed", exc_info=True)
    return entry


async def invalidate_resource_grants_for_team(team_id: UUID) -> None:
    """失效本进程 L1 + bump Redis 版本号 + 删除旧 Redis 数据条目。"""
    _LOCAL.pop(team_id, None)
    redis = await _get_redis()
    if redis is None:
        return
    try:
        # 先删除该 team 的所有版本数据条目，再 bump 版本号，确保读到旧版本的
        # worker 在 bump 后无法再命中旧条目
        async for key in redis.scan_iter(match=f"{_REDIS_PREFIX}{team_id}:v:*", count=128):
            await redis.delete(key)
        await redis.incr(f"{_REDIS_VERSION_KEY_PREFIX}{team_id}")
    except Exception:
        logger.warning("Redis resource grants invalidate failed", exc_info=True)


async def invalidate_all_resource_grants_cache() -> None:
    _LOCAL.clear()
    redis = await _get_redis()
    if redis is None:
        return
    try:
        async for key in redis.scan_iter(match=f"{_REDIS_PREFIX}*:v:*", count=128):
            await redis.delete(key)
        async for key in redis.scan_iter(match=f"{_REDIS_VERSION_KEY_PREFIX}*", count=128):
            await redis.delete(key)
    except Exception:
        logger.warning("Redis resource grants full invalidate failed", exc_info=True)


def clear_resource_grants_cache_for_tests() -> None:
    _LOCAL.clear()


def _get_local(
    team_id: UUID,
    *,
    current_version: str,
) -> ResourceGrantCacheEntry | None:
    """本地 L1 命中检查：TTL 兜底 + 版本号比对。"""
    hit = _LOCAL.get(team_id)
    if hit is None:
        return None
    entry, ts, stored_version = hit
    if time.monotonic() - ts >= _TTL_SEC:
        _LOCAL.pop(team_id, None)
        return None
    if current_version != stored_version:
        # 版本号变化：本进程 L1 已过期，丢弃并触发回源
        _LOCAL.pop(team_id, None)
        return None
    return entry


def _put_local(team_id: UUID, entry: ResourceGrantCacheEntry, version: str) -> None:
    if len(_LOCAL) >= _LOCAL_MAX:
        oldest = min(_LOCAL.items(), key=lambda item: item[1][1])[0]
        _LOCAL.pop(oldest, None)
    _LOCAL[team_id] = (entry, time.monotonic(), version)


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
    "ResourceGrantCacheEntry",
    "build_slug_to_personal_team_map",
    "clear_resource_grants_cache_for_tests",
    "get_cached_resource_grants",
    "invalidate_all_resource_grants_cache",
    "invalidate_resource_grants_for_team",
    "put_cached_resource_grants",
]
