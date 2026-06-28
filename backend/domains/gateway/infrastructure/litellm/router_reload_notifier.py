"""跨进程 Router 热重载通知

多 worker（如 K8s ``--workers 4``）部署下，``_router_instance`` 与若干 L1 进程内
缓存都是单例，凭据/模型更新时只有处理请求的那个 worker 会本地 ``reload_router``
并失效 L1，其余 worker 仍持有旧 model_list 与旧缓存，导致后续请求大概率命中旧配置。

本模块基于 Redis pub/sub 实现跨进程通知：

- 写入路径在本地重载完成后调用 :func:`publish_router_reload` 发布事件，可选携带
  ``tenant_id``；
- 每个 worker 在启动期通过 :func:`start_router_reload_subscriber` 订阅 channel，
  收到消息后：

  * 本地 ``reload_router``（重建 LiteLLM Router model_list）；
  * 按 ``tenant_id`` 失效该租户相关 L1 进程内缓存
    （resolve_model_cache / route_snapshot_cache / resource_grants_cache /
    quota_rule_cache）。``tenant_id`` 缺省时清空全部 L1。

  并按 ``event_id`` 做幂等去重，避免收到自己发的事件时重复刷新。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import Any
import uuid

from utils.logging import get_logger

logger = get_logger(__name__)

# Redis pub/sub channel：所有 worker 共享。
_CHANNEL = "gateway:router:reload"

# 订阅 task 句柄 + 关闭信号；模块级，单 worker 单订阅。
_subscriber_task: asyncio.Task[Any] | None = None
_subscriber_stop: asyncio.Event | None = None

# 已处理过的 event_id 去重集合；保留最近 N 条避免无界增长。
# 通常同一事件被一个 worker 处理一次即可，重复只在订阅重连/网络抖动时偶发。
_seen_event_ids: dict[str, float] = {}
_SEEN_MAX = 256


async def publish_router_reload(
    *,
    source: str = "write",
    tenant_id: uuid.UUID | None = None,
) -> None:
    """发布一次 Router 重载事件，通知所有 worker（含本进程）。

    本函数设计为 fire-and-forget：

    - 调用者已完成本地 ``reload_router`` 与本地 L1 失效；
    - 发布失败不应影响写入路径的事务结果，仅记录告警；
    - ``tenant_id`` 用于让订阅端按租户精准失效 L1；缺省表示"全量失效"。
    """
    try:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()
        event_id = uuid.uuid4().hex
        payload = json.dumps(
            {
                "event_id": event_id,
                "source": source,
                "origin_pid": os.getpid(),
                "tenant_id": str(tenant_id) if tenant_id is not None else None,
                "ts": asyncio.get_running_loop().time(),
            },
            ensure_ascii=False,
        )
        await client.publish(_CHANNEL, payload)
        logger.debug(
            "router reload published: event_id=%s source=%s tenant_id=%s",
            event_id,
            source,
            tenant_id,
        )
    except Exception:
        logger.warning(
            "router reload publish failed (multi-worker may go stale); source=%s",
            source,
            exc_info=True,
        )


def _remember_event_id(event_id: str) -> bool:
    """记录已处理事件 ID；返回 True 表示首次见到，应当处理。"""
    now = asyncio.get_running_loop().time()
    # 顺手淘汰过期项
    if len(_seen_event_ids) >= _SEEN_MAX:
        cutoff = now - 300
        stale = [k for k, t in _seen_event_ids.items() if t < cutoff]
        for k in stale:
            _seen_event_ids.pop(k, None)
    if event_id in _seen_event_ids:
        return False
    _seen_event_ids[event_id] = now
    return True


async def _invalidate_l1_for_tenant(tenant_id: uuid.UUID | None) -> None:
    """失效本进程内与该租户相关的 L1 读缓存。

    与写路径 ``_base.reload_litellm_router`` 内部的失效逻辑保持一致：tenant_id
    缺省时全量清空；提供时按租户精准失效。``quota_rule_cache`` 与
    ``resource_grants_cache`` 本身采用 Redis 版本号机制（写路径已 INCR 版本号），
    但本地 L1 仍按 tenant 清一遍以缩短生效延迟。
    """
    from domains.gateway.application.grant.resolve_model_cache import invalidate_all
    from domains.gateway.application.grant.resource_grants_cache import (
        _LOCAL as _RESOURCE_GRANTS_LOCAL,
    )
    from domains.gateway.application.observability.gateway_cache_invalidation import (
        invalidate_gateway_read_caches_for_tenant,
    )
    from domains.gateway.application.route.route_snapshot_cache import (
        clear_route_snapshot_cache_for_tests,
    )

    if tenant_id is not None:
        invalidate_gateway_read_caches_for_tenant(tenant_id)
        # resource_grants/quota_rule 的 Redis 失效（bump 版本号 + 删数据条目）
        # 已在写路径完成，本 worker 仅需清本地 L1 即可立即感知
        _RESOURCE_GRANTS_LOCAL.pop(tenant_id, None)
    else:
        invalidate_all()
        clear_route_snapshot_cache_for_tests()
        _RESOURCE_GRANTS_LOCAL.clear()


async def _handle_message(payload: str) -> None:
    """收到 pub/sub 消息后的处理：本地重载 Router + 失效 L1。"""
    try:
        data = json.loads(payload)
    except Exception:
        logger.warning("router reload subscriber got malformed payload: %r", payload)
        return
    event_id = data.get("event_id") or ""
    if not event_id or not _remember_event_id(event_id):
        return
    source = data.get("source") or "unknown"
    raw_tenant_id = data.get("tenant_id")
    tenant_id: uuid.UUID | None = None
    if isinstance(raw_tenant_id, str) and raw_tenant_id:
        try:
            tenant_id = uuid.UUID(raw_tenant_id)
        except ValueError:
            tenant_id = None
    logger.info(
        "router reload received from peer: event_id=%s source=%s tenant_id=%s",
        event_id,
        source,
        tenant_id,
    )
    # 先失效 L1，再 reload Router，避免 Router 重建查询时命中旧缓存
    try:
        await _invalidate_l1_for_tenant(tenant_id)
    except Exception:
        logger.warning("router reload L1 invalidation failed: event_id=%s", event_id, exc_info=True)
    try:
        from domains.gateway.infrastructure.litellm.router_singleton import reload_router
        from libs.db.database import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await reload_router(session)
    except Exception:
        logger.warning(
            "router reload on peer notification failed: event_id=%s",
            event_id,
            exc_info=True,
        )


async def start_router_reload_subscriber() -> None:
    """启动后台订阅 task。重复调用幂等。"""
    global _subscriber_task, _subscriber_stop
    if _subscriber_task is not None and not _subscriber_task.done():
        return
    _subscriber_stop = asyncio.Event()

    async def _run() -> None:
        from libs.db.redis import get_redis_client

        # 外层重连循环：Redis 不可用或连接断开后，每 5s 重试，直到 stop 信号
        while _subscriber_stop is not None and not _subscriber_stop.is_set():
            client: Any = None
            # 等待 Redis 可用：开发机可能未起 redis，订阅不应阻塞应用启动
            while _subscriber_stop is not None and not _subscriber_stop.is_set():
                try:
                    client = await get_redis_client()
                    break
                except Exception:
                    try:
                        await asyncio.wait_for(_subscriber_stop.wait(), timeout=5.0)
                        return
                    except TimeoutError:
                        continue
            if client is None:
                logger.warning("router reload subscriber stopped before redis became available")
                return

            pubsub = client.pubsub()
            try:
                await pubsub.subscribe(_CHANNEL)
                logger.info("router reload subscriber started: channel=%s", _CHANNEL)
            except Exception:
                logger.warning(
                    "router reload subscriber subscribe failed (retry in 5s)",
                    exc_info=True,
                )
                with contextlib.suppress(Exception):
                    await pubsub.aclose()
                try:
                    await asyncio.wait_for(_subscriber_stop.wait(), timeout=5.0)
                    return
                except TimeoutError:
                    continue

            try:
                async for message in pubsub.listen():
                    if _subscriber_stop is not None and _subscriber_stop.is_set():
                        break
                    if message.get("type") != "message":
                        continue
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    if not isinstance(data, str):
                        continue
                    try:
                        await _handle_message(data)
                    except Exception:
                        logger.warning("router reload subscriber handler error", exc_info=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning(
                    "router reload subscriber loop error (will reconnect in 5s)",
                    exc_info=True,
                )
            finally:
                try:
                    await pubsub.unsubscribe(_CHANNEL)
                    await pubsub.aclose()
                except Exception:
                    pass
                logger.info("router reload subscriber disconnected")

            # 短暂退避后重连，避免 tight loop
            if _subscriber_stop is not None and not _subscriber_stop.is_set():
                try:
                    await asyncio.wait_for(_subscriber_stop.wait(), timeout=5.0)
                    return
                except TimeoutError:
                    continue

        logger.info("router reload subscriber stopped")

    _subscriber_task = asyncio.create_task(_run(), name="router_reload_subscriber")


async def stop_router_reload_subscriber() -> None:
    """停止订阅 task。应用关闭时调用。"""
    global _subscriber_task, _subscriber_stop
    if _subscriber_stop is not None:
        _subscriber_stop.set()
    if _subscriber_task is not None:
        task = _subscriber_task
        _subscriber_task = None
        if not task.done():
            task.cancel()
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2.0)
    _subscriber_stop = None


__all__ = [
    "publish_router_reload",
    "start_router_reload_subscriber",
    "stop_router_reload_subscriber",
]
