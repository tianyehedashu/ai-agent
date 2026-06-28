"""``resolve_model_or_route`` 进程内 LRU + Redis 版本号机制。

正缓存保存 ``ResolvedModelName`` 的纯值快照，避免把 SQLAlchemy ORM 实例带出原 Session；
负缓存保存无解析结果标记。

跨进程一致性：写路径（凭据/模型/路由变更）通过 :func:`invalidate_for_tenant`
bump Redis 版本号 ``gw:resolve_model:ver:<tenant>``；所有 worker 读路径比较本地
版本号决定是否过期，避免单纯 TTL 在多 worker 下最长 60s 的旧值窗口。

降级：Redis 不可用时退化为单调时钟 TTL（行为与旧版一致）。
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.gateway.application.catalog.model_or_route_resolution import ResolvedModelName

logger = get_logger(__name__)

_NEGATIVE_ENTRY = object()  # 负缓存标记（无 resolve）
_CACHE: dict[tuple[UUID, UUID | None, str], tuple[object, float, str]] = {}
"""key → (payload, ts, version)。``version`` 为写入时该租户的 Redis 版本号。"""

_TTL_SEC = 60.0
_MAX_ENTRIES = 4096

CACHE_MISS = object()

# Redis 版本号 key 前缀；写路径 INCR 之，读路径 GET 之。
_REDIS_VERSION_KEY_PREFIX = "gw:resolve_model:ver:"

# 本进程对 tenant_id → 最新已知版本号的缓存（避免每次读缓存都打 Redis）。
# 在 Redis 不可用或读取失败时退化为空串，等价于"版本号总是变化"，即触发本
# 进程内条目按 TTL 自然过期（保持向后兼容）。
_TENANT_VERSION_L1: dict[UUID, str] = {}
_TENANT_VERSION_L1_TTL = 5.0  # 秒：限流对 Redis 的版本号 GET
_TENANT_VERSION_TS: dict[UUID, float] = {}

# fire-and-forget task 强引用集合，避免被 GC；完成后自动 discard
_PENDING_BUMP_TASKS: set[asyncio.Task[Any]] = set()


def _cache_key(team_id: UUID, name: str, *, user_id: UUID | None) -> tuple[UUID, UUID | None, str]:
    return (team_id, user_id, name.strip())


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
        # Redis 异常：保留旧版本号缓存，避免抖动导致缓存雪崩
        return cached or ""
    _TENANT_VERSION_L1[team_id] = version
    _TENANT_VERSION_TS[team_id] = now
    return version


async def peek_resolve_cache_entry(
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
    payload, ts, stored_version = hit
    # 1) 单调时钟 TTL 兜底
    if time.monotonic() - ts >= _TTL_SEC:
        _CACHE.pop(key, None)
        return CACHE_MISS
    # 2) Redis 版本号变化 → 失效
    current_version = await _fetch_tenant_version(team_id)
    if current_version != stored_version:
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
    version: str | None = None,
) -> None:
    """写入缓存。``version`` 由读路径填充（来自 :func:`_fetch_tenant_version` 的快照）。"""
    cleaned = name.strip()
    if not cleaned:
        return
    if len(_CACHE) >= _MAX_ENTRIES:
        _evict_oldest()
    key = _cache_key(team_id, cleaned, user_id=user_id)
    if resolved is None:
        payload = _NEGATIVE_ENTRY
    else:
        from domains.gateway.application.catalog.model_or_route_resolution import (
            cache_safe_resolved_model_name,
        )

        payload = cache_safe_resolved_model_name(resolved)
    _CACHE[key] = (payload, time.monotonic(), version or "")


def invalidate_for_tenant(tenant_id: UUID) -> None:
    """失效本进程 L1 + 异步 bump Redis 版本号，通知所有 worker。

    同步签名：本地 L1 立即清空；Redis 版本号 INCR 通过 ``create_task`` fire-and-
    forget 异步执行，避免把网络 IO 强加到调用方。无运行中事件循环（如启动期
    维护逻辑）时退化为同步尝试。

    保留 task 强引用避免 GC（Python 文档要求）；任务完成后自动从集合移除。
    """
    keys = [k for k in _CACHE if k[0] == tenant_id]
    for key in keys:
        _CACHE.pop(key, None)
    # 清除版本号 L1，强制下次读路径重新拉取
    _TENANT_VERSION_L1.pop(tenant_id, None)
    _TENANT_VERSION_TS.pop(tenant_id, None)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # 没有运行中的事件循环，无法发布跨进程通知；保留本地 L1 失效即可
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
            "resolve_model_cache version bump failed: tenant_id=%s", tenant_id, exc_info=True
        )


def invalidate_all() -> None:
    _CACHE.clear()
    _TENANT_VERSION_L1.clear()
    _TENANT_VERSION_TS.clear()


def clear_resolve_model_cache_for_tests() -> None:
    _CACHE.clear()
    _TENANT_VERSION_L1.clear()
    _TENANT_VERSION_TS.clear()
    for task in list(_PENDING_BUMP_TASKS):
        task.cancel()
    _PENDING_BUMP_TASKS.clear()


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
