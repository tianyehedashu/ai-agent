"""Platform 预算窗口用量落库（proxy / callback 成功后异步合并刷写）。

跨路径 / 跨 worker 去重经 Redis ``SET NX``（每个 ``(request_id, source)`` 仅一次），
通过去重后的增量按桶键合并、批量 upsert（见 ``usage_bucket_flusher``），消除热桶行锁串行化。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
import uuid

from domains.gateway.application.usage_bucket_flusher import record_bucket_usage
from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
    compute_period_window_start,
)
from domains.gateway.domain.quota_plan import PLATFORM_NS, UsageBucketNamespace
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)

PlatformBucketUpsertSource = Literal["proxy", "callback"]

_BUCKET_UPSERTED_PREFIX = "gateway:quota:{ns}_bucket_upserted:"
_BUCKET_UPSERTED_TTL_SECONDS = 86400


@dataclass(frozen=True)
class PlatformBudgetUpsertItem:
    budget_id: uuid.UUID
    period: str
    period_reset_anchor: PeriodResetAnchor = DEFAULT_PERIOD_RESET_ANCHOR


def _bucket_upserted_key(
    ns: UsageBucketNamespace,
    request_id: str,
    source: PlatformBucketUpsertSource,
) -> str:
    return f"{_BUCKET_UPSERTED_PREFIX.format(ns=ns)}{request_id}:{source}"


async def _acquire_bucket_upsert_once(
    ns: UsageBucketNamespace,
    request_id: str,
    source: PlatformBucketUpsertSource,
) -> bool:
    client = await get_redis_client()
    acquired = await client.set(
        _bucket_upserted_key(ns, request_id, source),
        "1",
        nx=True,
        ex=_BUCKET_UPSERTED_TTL_SECONDS,
    )
    return bool(acquired)


async def schedule_platform_budget_usage_upsert(
    *,
    items: list[PlatformBudgetUpsertItem],
    delta_tokens: int,
    delta_cost_usd: Decimal,
    delta_requests: int = 1,
    delta_images: int = 0,
    request_id: str | None,
    source: PlatformBucketUpsertSource = "proxy",
    settled_at: datetime | None = None,
) -> None:
    """去重后把 platform 窗口用量增量记入合并刷写器（不阻塞 proxy / callback）。"""
    if not items or not request_id:
        return
    if not await _acquire_bucket_upsert_once(PLATFORM_NS, request_id, source):
        return
    when = settled_at or datetime.now(UTC)
    for item in items:
        window_start = compute_period_window_start(
            when,
            item.period,
            item.period_reset_anchor,
        )
        record_bucket_usage(
            PLATFORM_NS,
            item.budget_id,
            item.budget_id,
            window_start,
            delta_tokens=delta_tokens,
            delta_cost_usd=delta_cost_usd,
            delta_requests=delta_requests,
            delta_images=delta_images,
        )


__all__ = [
    "PlatformBucketUpsertSource",
    "PlatformBudgetUpsertItem",
    "schedule_platform_budget_usage_upsert",
]
