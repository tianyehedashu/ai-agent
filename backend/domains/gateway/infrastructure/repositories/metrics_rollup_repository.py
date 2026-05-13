"""Gateway 请求日志 → 小时指标 rollup（基础设施写路径）"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domains.gateway.infrastructure.models.metrics_hourly import GatewayMetricsHourly
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayMetricsRollupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def rollup_window(self, since: datetime, until: datetime) -> int:
        """把 [since, until) 区间的 logs 聚合到 metrics_hourly 并提交。"""
        bucket = func.date_trunc("hour", GatewayRequestLog.created_at)
        stmt = (
            select(
                bucket.label("bucket_at"),
                GatewayRequestLog.team_id,
                GatewayRequestLog.user_id,
                GatewayRequestLog.vkey_id,
                GatewayRequestLog.provider,
                GatewayRequestLog.real_model,
                GatewayRequestLog.capability,
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(
                    case((GatewayRequestLog.status == "success", 1), else_=0)
                ).label("success_count"),
                func.sum(
                    case((GatewayRequestLog.status != "success", 1), else_=0)
                ).label("error_count"),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.sum(GatewayRequestLog.latency_ms).label("total_latency_ms"),
                func.sum(
                    case((GatewayRequestLog.cache_hit.is_(True), 1), else_=0)
                ).label("cache_hit_count"),
            )
            .where(
                GatewayRequestLog.created_at >= since,
                GatewayRequestLog.created_at < until,
            )
            .group_by(
                bucket,
                GatewayRequestLog.team_id,
                GatewayRequestLog.user_id,
                GatewayRequestLog.vkey_id,
                GatewayRequestLog.provider,
                GatewayRequestLog.real_model,
                GatewayRequestLog.capability,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        upserted = 0
        for row in rows:
            values = {
                "id": uuid.uuid4(),
                "bucket_at": row.bucket_at,
                "team_id": row.team_id,
                "user_id": row.user_id,
                "vkey_id": row.vkey_id,
                "provider": row.provider,
                "real_model": row.real_model,
                "capability": row.capability,
                "requests": int(row.requests or 0),
                "success_count": int(row.success_count or 0),
                "error_count": int(row.error_count or 0),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "cached_tokens": int(row.cached_tokens or 0),
                "cost_usd": Decimal(row.cost_usd or 0),
                "total_latency_ms": int(row.total_latency_ms or 0),
                "p95_latency_ms": 0,
                "cache_hit_count": int(row.cache_hit_count or 0),
            }
            stmt_upsert = pg_insert(GatewayMetricsHourly).values(**values)
            update_cols = {k: stmt_upsert.excluded[k] for k in values if k != "id"}
            await self._session.execute(
                stmt_upsert.on_conflict_do_update(
                    constraint="uq_gateway_metrics_hourly_dim",
                    set_=update_cols,
                )
            )
            upserted += 1
        await self._session.commit()
        return upserted


__all__ = ["GatewayMetricsRollupRepository"]
