"""虚拟 Key 使用回写：合并写入，消除单行 UPDATE 写热点。

每次 ``sk-gw-`` 调用都对同一行做 ``UPDATE ... usage_count = usage_count + 1`` 时，
PostgreSQL 行级排他锁会把并发更新串行化；高 QPS 的热门 vkey 因此产生大量「等锁」慢查询，
且无上限的 fire-and-forget 任务会占满后台连接池，拖累请求日志 / 预算 / 配额结算。

本模块改为：热路径仅在进程内累加 ``usage_count`` 增量与 ``last_used_at``，
由通用 ``CoalescingFlusher`` 批量落库（``usage_count = usage_count + Δ``、
``last_used_at = GREATEST(last_used_at, ts)``，相对自增跨 worker 仍正确）。

``gateway_vkey_usage_flush_interval_seconds=0`` 时回退为即时单条写入（安全降级）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
import uuid

from sqlalchemy import text

from bootstrap.config import settings
from domains.gateway.application.proxy.proxy_deferred_tasks import register_proxy_deferred_task
from domains.gateway.infrastructure.repositories.virtual_key_repository import (
    VirtualKeyRepository,
)
from libs.concurrency import CoalescingFlusher
from libs.db.database import get_session_context, prefer_background_pool
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _PendingUsage:
    """单个 vkey 在当前窗口累计的用量增量与最近使用时间。"""

    delta: int
    last_used_at: datetime


def _merge_usage(existing: _PendingUsage, new: _PendingUsage) -> _PendingUsage:
    existing.delta += new.delta
    existing.last_used_at = max(existing.last_used_at, new.last_used_at)
    return existing


async def _flush_usage(entries: list[tuple[uuid.UUID, _PendingUsage]]) -> None:
    with prefer_background_pool():
        async with get_session_context() as session:
            timeout_ms = int(settings.gateway_vkey_usage_flush_statement_timeout_ms)
            if timeout_ms > 0:
                await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            await VirtualKeyRepository(session).bulk_increment_usage(
                [(vkey_id, p.delta, p.last_used_at) for vkey_id, p in entries]
            )


_flusher: CoalescingFlusher[uuid.UUID, _PendingUsage] = CoalescingFlusher(
    name="vkey-usage",
    merge=_merge_usage,
    flush=_flush_usage,
    interval_seconds=lambda: float(settings.gateway_vkey_usage_flush_interval_seconds),
    max_pending=lambda: int(settings.gateway_vkey_usage_flush_max_pending),
    register_task=register_proxy_deferred_task,
)


async def _touch_virtual_key_used_now(vkey_id: uuid.UUID) -> None:
    """即时单条写入（合并关闭时的降级路径）。"""
    try:
        with prefer_background_pool():
            async with get_session_context() as session:
                await VirtualKeyRepository(session).touch_used(vkey_id)
    except Exception:
        logger.exception("Async vkey touch_used failed for %s", vkey_id)


def schedule_virtual_key_touch(vkey_id: uuid.UUID) -> None:
    """登记 vkey 使用回写（不阻塞鉴权热路径）。

    默认合并写入；``gateway_vkey_usage_flush_interval_seconds=0`` 时降级为即时单条写。
    """
    if float(settings.gateway_vkey_usage_flush_interval_seconds) <= 0:
        task = asyncio.create_task(_touch_virtual_key_used_now(vkey_id))
        register_proxy_deferred_task(task)
        return
    _flusher.add(vkey_id, _PendingUsage(delta=1, last_used_at=datetime.now(UTC)))


__all__ = ["schedule_virtual_key_touch"]
