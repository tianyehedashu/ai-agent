"""Platform 预算窗口用量异步落库（proxy / callback 成功后 fire-and-forget）。"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
import uuid

from domains.gateway.application.proxy_deferred_tasks import register_proxy_deferred_task
from domains.gateway.domain.platform_budget_window import compute_platform_budget_window_start
from domains.gateway.domain.quota_plan import PLATFORM_NS, UsageBucketNamespace
from domains.gateway.infrastructure.repositories.quota_plan_usage_bucket_repository import (
    QuotaPlanUsageBucketRepository,
)
from libs.db.database import get_session_context
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


async def _release_bucket_upsert_once(
    ns: UsageBucketNamespace,
    request_id: str,
    source: PlatformBucketUpsertSource,
) -> None:
    client = await get_redis_client()
    await client.delete(_bucket_upserted_key(ns, request_id, source))


async def _upsert_platform_budget_usage(
    *,
    items: list[PlatformBudgetUpsertItem],
    delta_tokens: int,
    delta_cost_usd: Decimal,
    delta_requests: int,
    request_id: str,
    source: PlatformBucketUpsertSource,
    settled_at: datetime,
) -> None:
    if not items:
        return
    if not await _acquire_bucket_upsert_once(PLATFORM_NS, request_id, source):
        return
    try:
        async with get_session_context() as session:
            repo = QuotaPlanUsageBucketRepository(session)
            for item in items:
                window_start = compute_platform_budget_window_start(settled_at, item.period)
                await repo.increment_bucket(
                    PLATFORM_NS,
                    item.budget_id,
                    item.budget_id,
                    window_start,
                    delta_tokens=delta_tokens,
                    delta_requests=delta_requests,
                    delta_cost_usd=delta_cost_usd,
                )
            await session.commit()
    except Exception:
        logger.exception(
            "Async platform budget usage bucket upsert failed request=%s source=%s items=%d",
            request_id,
            source,
            len(items),
        )
        with suppress(Exception):
            await _release_bucket_upsert_once(PLATFORM_NS, request_id, source)


def schedule_platform_budget_usage_upsert(
    *,
    items: list[PlatformBudgetUpsertItem],
    delta_tokens: int,
    delta_cost_usd: Decimal,
    delta_requests: int = 1,
    request_id: str | None,
    source: PlatformBucketUpsertSource = "proxy",
    settled_at: datetime | None = None,
) -> None:
    """登记后台任务 upsert platform 窗口用量汇总（不阻塞 proxy / callback）。"""
    if not items or not request_id:
        return
    when = settled_at or datetime.now(UTC)
    task = asyncio.create_task(
        _upsert_platform_budget_usage(
            items=items,
            delta_tokens=delta_tokens,
            delta_cost_usd=delta_cost_usd,
            delta_requests=delta_requests,
            request_id=request_id,
            source=source,
            settled_at=when,
        )
    )
    register_proxy_deferred_task(task)


__all__ = [
    "PlatformBucketUpsertSource",
    "PlatformBudgetUpsertItem",
    "schedule_platform_budget_usage_upsert",
]
