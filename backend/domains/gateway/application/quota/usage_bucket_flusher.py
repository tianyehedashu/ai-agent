"""配额/预算窗口桶用量合并刷写：消除「当期热桶被每请求 UPDATE」的行锁串行化。

Platform 预算桶与上下游套餐配额桶都落在同一张 ``gateway_quota_plan_usage_bucket``
（platform 即 ``ns=PLATFORM_NS``、``plan_id=quota_id=budget_id``），且当期窗口行会被同团队/套餐
的每个请求做 ``UPDATE ... col = col + Δ``，与 vkey 同病。本模块把增量按桶键
``(ns, plan_id, quota_id, window_start)`` 在进程内累加，由通用 ``CoalescingFlusher`` 批量 upsert。

跨路径（proxy / callback）与跨 worker 去重仍由调用方在 **记录前** 用 Redis ``SET NX`` 完成
（见 ``budget_usage_persist`` / ``quota_plan_usage_persist``），故合并的都是「已去重」的增量，
求和正确。落库失败由 flusher 并回重试，不丢账（进程崩溃会丢未刷增量，与 vkey 同口径取舍）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import text

from bootstrap.config import settings
from domains.gateway.application.proxy.proxy_deferred_tasks import register_proxy_deferred_task
from domains.gateway.domain.quota.quota_plan import UsageBucketNamespace
from domains.gateway.infrastructure.repositories.quota_plan_usage_bucket_repository import (
    QuotaPlanUsageBucketRepository,
)
from libs.concurrency import CoalescingFlusher
from libs.db.database import get_session_context, prefer_background_pool

BucketKey = tuple[UsageBucketNamespace, uuid.UUID, uuid.UUID, datetime]


@dataclass
class _PendingBucket:
    """单个窗口桶在当前刷写窗口内累计的增量。"""

    delta_tokens: int
    delta_cost_usd: Decimal
    delta_requests: int
    delta_images: int = 0


def _merge_bucket(existing: _PendingBucket, new: _PendingBucket) -> _PendingBucket:
    existing.delta_tokens += new.delta_tokens
    existing.delta_cost_usd += new.delta_cost_usd
    existing.delta_requests += new.delta_requests
    existing.delta_images += new.delta_images
    return existing


async def _flush_buckets(entries: list[tuple[BucketKey, _PendingBucket]]) -> None:
    with prefer_background_pool():
        async with get_session_context() as session:
            timeout_ms = int(settings.gateway_usage_bucket_flush_statement_timeout_ms)
            if timeout_ms > 0:
                await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            repo = QuotaPlanUsageBucketRepository(session)
            for (ns, plan_id, quota_id, window_start), pending in entries:
                await repo.increment_bucket(
                    ns,
                    plan_id,
                    quota_id,
                    window_start,
                    delta_tokens=pending.delta_tokens,
                    delta_requests=pending.delta_requests,
                    delta_cost_usd=pending.delta_cost_usd,
                    delta_images=pending.delta_images,
                )


_bucket_flusher: CoalescingFlusher[BucketKey, _PendingBucket] = CoalescingFlusher(
    name="usage-bucket",
    merge=_merge_bucket,
    flush=_flush_buckets,
    interval_seconds=lambda: float(settings.gateway_usage_bucket_flush_interval_seconds),
    max_pending=lambda: int(settings.gateway_usage_bucket_flush_max_pending),
    register_task=register_proxy_deferred_task,
)


def coalescing_enabled() -> bool:
    return float(settings.gateway_usage_bucket_flush_interval_seconds) > 0


def record_bucket_usage(
    ns: UsageBucketNamespace,
    plan_id: uuid.UUID,
    quota_id: uuid.UUID,
    window_start: datetime,
    *,
    delta_tokens: int,
    delta_cost_usd: Decimal,
    delta_requests: int,
    delta_images: int = 0,
) -> None:
    """累加一个窗口桶增量；关闭合并时立即补刷一次（行为等价即时落库）。"""
    _bucket_flusher.add(
        (ns, plan_id, quota_id, window_start),
        _PendingBucket(
            delta_tokens=delta_tokens,
            delta_cost_usd=delta_cost_usd,
            delta_requests=delta_requests,
            delta_images=delta_images,
        ),
    )
    if not coalescing_enabled():
        _bucket_flusher.flush_soon()


__all__ = ["BucketKey", "coalescing_enabled", "record_bucket_usage"]
