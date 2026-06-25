"""Gateway 请求日志 → 小时指标 rollup（基础设施写路径）"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from domains.gateway.infrastructure.models.metrics_hourly import GatewayMetricsHourly
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_METRIC_ACCUMULATE_COLUMNS = (
    "requests",
    "success_count",
    "error_count",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "cache_creation_tokens",
    "cost_usd",
    "revenue_usd",
    "total_latency_ms",
    "ttfb_total_ms",
    "cache_hit_count",
)

_UPSERT_DIMENSION_COLUMNS = (
    "bucket_at",
    "tenant_id",
    "user_id",
    "resource_owner_user_id",
    "vkey_id",
    "credential_id",
    "entitlement_plan_id",
    "provider_plan_id",
    "provider",
    "model_key",
    "capability",
)


class RollupUpsertMode(str, Enum):
    INCREMENT = "increment"
    REPLACE = "replace"


def _request_log_model_key_expr():
    return func.coalesce(
        func.nullif(func.trim(GatewayRequestLog.deployment_model_name), ""),
        func.nullif(func.trim(GatewayRequestLog.route_name), ""),
        func.nullif(func.trim(GatewayRequestLog.real_model), ""),
        "unknown",
    )


class GatewayMetricsRollupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def rollup_window(
        self,
        since: datetime,
        until: datetime,
        *,
        mode: RollupUpsertMode = RollupUpsertMode.INCREMENT,
    ) -> int:
        """把 [since, until) 区间的 logs 聚合到 metrics_hourly（不 commit，由调用方与 watermark 同事务提交）。"""
        if mode is RollupUpsertMode.REPLACE:
            await self._delete_hourly_in_window(since, until)

        bucket = func.date_trunc("hour", GatewayRequestLog.created_at)
        model_key = _request_log_model_key_expr()
        stmt = (
            select(
                bucket.label("bucket_at"),
                GatewayRequestLog.tenant_id,
                GatewayRequestLog.user_id,
                GatewayRequestLog.resource_owner_user_id,
                GatewayRequestLog.vkey_id,
                GatewayRequestLog.credential_id,
                GatewayRequestLog.entitlement_plan_id,
                GatewayRequestLog.provider_plan_id,
                GatewayRequestLog.provider,
                func.max(GatewayRequestLog.real_model).label("real_model"),
                model_key.label("model_key"),
                GatewayRequestLog.capability,
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(case((GatewayRequestLog.status == "success", 1), else_=0)).label(
                    "success_count"
                ),
                func.sum(case((GatewayRequestLog.status != "success", 1), else_=0)).label(
                    "error_count"
                ),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.sum(GatewayRequestLog.revenue_usd).label("revenue_usd"),
                func.sum(
                    case(
                        (GatewayRequestLog.status == "success", GatewayRequestLog.latency_ms),
                        else_=0,
                    )
                ).label("total_latency_ms"),
                func.sum(
                    case(
                        (GatewayRequestLog.status == "success", GatewayRequestLog.ttfb_ms),
                        else_=0,
                    )
                ).label("ttfb_total_ms"),
                func.sum(case((GatewayRequestLog.cache_hit.is_(True), 1), else_=0)).label(
                    "cache_hit_count"
                ),
            )
            .where(
                GatewayRequestLog.created_at >= since,
                GatewayRequestLog.created_at < until,
            )
            .group_by(
                bucket,
                GatewayRequestLog.tenant_id,
                GatewayRequestLog.user_id,
                GatewayRequestLog.resource_owner_user_id,
                GatewayRequestLog.vkey_id,
                GatewayRequestLog.credential_id,
                GatewayRequestLog.entitlement_plan_id,
                GatewayRequestLog.provider_plan_id,
                GatewayRequestLog.provider,
                model_key,
                GatewayRequestLog.capability,
            )
        )
        rows = (await self._session.execute(stmt)).all()
        if not rows:
            return 0

        values_list = [
            {
                "id": uuid.uuid4(),
                "bucket_at": row.bucket_at,
                "tenant_id": row.tenant_id,
                "user_id": row.user_id,
                "vkey_id": row.vkey_id,
                "credential_id": row.credential_id,
                "entitlement_plan_id": row.entitlement_plan_id,
                "provider_plan_id": row.provider_plan_id,
                "provider": row.provider,
                "real_model": row.real_model,
                "resource_owner_user_id": row.resource_owner_user_id,
                "model_key": row.model_key,
                "capability": row.capability,
                "requests": int(row.requests or 0),
                "success_count": int(row.success_count or 0),
                "error_count": int(row.error_count or 0),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "cached_tokens": int(row.cached_tokens or 0),
                "cache_creation_tokens": int(row.cache_creation_tokens or 0),
                "cost_usd": Decimal(row.cost_usd or 0),
                "revenue_usd": Decimal(row.revenue_usd or 0),
                "total_latency_ms": int(row.total_latency_ms or 0),
                "ttfb_total_ms": int(row.ttfb_total_ms or 0),
                "p95_latency_ms": 0,
                "cache_hit_count": int(row.cache_hit_count or 0),
            }
            for row in rows
        ]
        stmt_upsert = pg_insert(GatewayMetricsHourly).values(values_list)
        excluded = stmt_upsert.excluded
        if mode is RollupUpsertMode.INCREMENT:
            update_cols = {
                col: getattr(GatewayMetricsHourly, col) + getattr(excluded, col)
                for col in _METRIC_ACCUMULATE_COLUMNS
            }
            update_cols["real_model"] = excluded.real_model
            update_cols["p95_latency_ms"] = GatewayMetricsHourly.p95_latency_ms
        else:
            update_cols = {col: getattr(excluded, col) for col in _METRIC_ACCUMULATE_COLUMNS}
            update_cols["real_model"] = excluded.real_model
            update_cols["p95_latency_ms"] = excluded.p95_latency_ms

        await self._session.execute(
            stmt_upsert.on_conflict_do_update(
                constraint="uq_gateway_metrics_hourly_dim",
                set_=update_cols,
            )
        )
        await self._session.flush()
        return len(values_list)

    async def _delete_hourly_in_window(self, since: datetime, until: datetime) -> None:
        await self._session.execute(
            delete(GatewayMetricsHourly).where(
                GatewayMetricsHourly.bucket_at >= since,
                GatewayMetricsHourly.bucket_at < until,
            )
        )


__all__ = ["GatewayMetricsRollupRepository", "RollupUpsertMode"]
