"""上下游套餐配额窗口用量落库（callback / proxy 成功后异步合并刷写）。

跨路径 / 跨 worker 去重经 Redis ``SET NX``（每个 ``request_id`` 仅一次），通过去重后的增量
按桶键合并、批量 upsert（见 ``usage_bucket_flusher``），消除当期热桶行锁串行化。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from domains.gateway.application.usage_bucket_flusher import record_bucket_usage
from domains.gateway.domain.quota_plan import (
    PlanQuotaSpec,
    QuotaPlanNamespace,
    compute_window_start_datetime,
    is_sliding_rolling_window,
)
from libs.db.redis import get_redis_client
from utils.logging import get_logger

logger = get_logger(__name__)

_BUCKET_UPSERTED_PREFIX = "gateway:quota:{ns}_bucket_upserted:"
_BUCKET_UPSERTED_TTL_SECONDS = 86400


def _bucket_upserted_key(ns: QuotaPlanNamespace, request_id: str) -> str:
    return _BUCKET_UPSERTED_PREFIX.format(ns=ns) + request_id


async def _acquire_bucket_upsert_once(ns: QuotaPlanNamespace, request_id: str) -> bool:
    client = await get_redis_client()
    acquired = await client.set(
        _bucket_upserted_key(ns, request_id),
        "1",
        nx=True,
        ex=_BUCKET_UPSERTED_TTL_SECONDS,
    )
    return bool(acquired)


async def schedule_quota_plan_usage_upsert(
    *,
    ns: QuotaPlanNamespace,
    plan_id: uuid.UUID,
    specs: list[PlanQuotaSpec],
    delta_tokens: int,
    delta_cost_usd: Decimal,
    delta_requests: int = 1,
    request_id: str | None,
    settled_at: datetime | None = None,
) -> None:
    """去重后把套餐配额窗口用量增量记入合并刷写器（不阻塞 callback / proxy）。"""
    if not specs or not request_id:
        return
    # 真正的滚动窗口（window_seconds>0 且 rolling）window_start 每分钟滑动，落桶会产生每分钟
    # 一行的垃圾且无法被读路径正确命中（详见 quota_plan_usage_reads），故不落 PG 桶、展示读直接
    # 聚合日志。window_seconds<=0 的累计（总额）即便策略名是 rolling 也按固定累计正常落桶。
    persist_specs = [
        spec for spec in specs if not is_sliding_rolling_window(spec.window_seconds, spec.reset_strategy)
    ]
    if not persist_specs:
        return
    if not await _acquire_bucket_upsert_once(ns, request_id):
        return
    when = settled_at or datetime.now(UTC)
    for spec in persist_specs:
        window_start = compute_window_start_datetime(
            when,
            spec.window_seconds,
            strategy=spec.reset_strategy,
            row_valid_from=None,
            period_reset_anchor=spec.period_reset_anchor,
        )
        record_bucket_usage(
            ns,
            plan_id,
            spec.quota_id,
            window_start,
            delta_tokens=delta_tokens,
            delta_cost_usd=delta_cost_usd,
            delta_requests=delta_requests,
        )


__all__ = ["schedule_quota_plan_usage_upsert"]
