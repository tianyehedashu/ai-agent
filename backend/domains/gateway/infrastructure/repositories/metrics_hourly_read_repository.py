"""gateway_metrics_hourly 读路径仓储（Dashboard/Statistics hybrid 冷段）。"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import case, func, literal, or_, select

from domains.gateway.domain.usage.usage_read_model import (
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
    UsageStatisticsParentScope,
)
from domains.gateway.infrastructure.models.metrics_hourly import GatewayMetricsHourly
from domains.gateway.infrastructure.repositories.metrics_hourly_axis_sql import (
    metrics_hourly_and,
    metrics_hourly_axis_clauses,
    metrics_hourly_time_clauses,
)
from domains.gateway.infrastructure.repositories.request_log_repository import (
    BreakdownPairRow,
    RequestLogUsageAggregateRow,
    RequestLogUsageTotals,
)

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.domain.usage.usage_axis import UsageAxis


class MetricsHourlyReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _model_filter_clause(model: str):
        return or_(
            GatewayMetricsHourly.model_key == model,
            GatewayMetricsHourly.real_model == model,
        )

    @staticmethod
    def _list_filter_clauses(
        *,
        capability: str | None = None,
        vkey_id: UUID | None = None,
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
        model: str | None = None,
    ) -> list:
        clauses: list = []
        if capability is not None:
            clauses.append(GatewayMetricsHourly.capability == capability)
        if vkey_id is not None:
            clauses.append(GatewayMetricsHourly.vkey_id == vkey_id)
        if credential_id is not None:
            clauses.append(GatewayMetricsHourly.credential_id == credential_id)
        if user_id is not None:
            clauses.append(GatewayMetricsHourly.user_id == user_id)
        if model is not None:
            clauses.append(MetricsHourlyReadRepository._model_filter_clause(model))
        return clauses

    @staticmethod
    def _statistics_filter_clauses(filters: UsageStatisticsFilters) -> list:
        clauses: list = []
        if filters.credential_id is not None:
            clauses.append(GatewayMetricsHourly.credential_id == filters.credential_id)
        if filters.user_id is not None:
            clauses.append(GatewayMetricsHourly.user_id == filters.user_id)
        if filters.team_id is not None:
            clauses.append(GatewayMetricsHourly.tenant_id == filters.team_id)
        if filters.vkey_id is not None:
            clauses.append(GatewayMetricsHourly.vkey_id == filters.vkey_id)
        if filters.model is not None:
            clauses.append(MetricsHourlyReadRepository._model_filter_clause(filters.model))
        if filters.provider is not None:
            clauses.append(GatewayMetricsHourly.provider == filters.provider)
        if filters.capability is not None:
            clauses.append(GatewayMetricsHourly.capability == filters.capability)
        return clauses

    @staticmethod
    def _group_exprs(group_by: UsageStatisticsGroupBy) -> list:
        if group_by == UsageStatisticsGroupBy.CREDENTIAL:
            return [GatewayMetricsHourly.credential_id]
        if group_by == UsageStatisticsGroupBy.USER:
            return [GatewayMetricsHourly.user_id]
        if group_by == UsageStatisticsGroupBy.TEAM:
            return [GatewayMetricsHourly.tenant_id]
        if group_by == UsageStatisticsGroupBy.MODEL:
            return [GatewayMetricsHourly.model_key]
        if group_by == UsageStatisticsGroupBy.VKEY:
            return [GatewayMetricsHourly.vkey_id]
        if group_by == UsageStatisticsGroupBy.PROVIDER:
            return [GatewayMetricsHourly.provider]
        if group_by == UsageStatisticsGroupBy.CAPABILITY:
            return [GatewayMetricsHourly.capability]
        if group_by == UsageStatisticsGroupBy.STATUS:
            raise ValueError("status group_by not supported on metrics_hourly")
        if group_by == UsageStatisticsGroupBy.USER_MODEL_CREDENTIAL:
            raise ValueError("user_model_credential group_by not supported on metrics_hourly")
        raise ValueError(f"Unknown usage statistics group_by: {group_by!r}")

    async def aggregate_summary_by_axis(
        self,
        axis: UsageAxis,
        bucket_start: datetime,
        bucket_end_exclusive: datetime,
        *,
        capability: str | None = None,
        vkey_id: UUID | None = None,
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        clauses = [
            *metrics_hourly_axis_clauses(axis),
            *metrics_hourly_time_clauses(bucket_start, bucket_end_exclusive),
            *self._list_filter_clauses(
                capability=capability,
                vkey_id=vkey_id,
                credential_id=credential_id,
                user_id=user_id,
                model=model,
            ),
        ]
        latency_weight = func.sum(
            case((GatewayMetricsHourly.success_count > 0, GatewayMetricsHourly.total_latency_ms), else_=0)
        )
        ttfb_weight = func.sum(
            case((GatewayMetricsHourly.success_count > 0, GatewayMetricsHourly.ttfb_total_ms), else_=0)
        )
        success_weight = func.sum(GatewayMetricsHourly.success_count)
        stmt = select(
            func.sum(GatewayMetricsHourly.requests).label("total"),
            func.sum(GatewayMetricsHourly.input_tokens).label("input_tokens"),
            func.sum(GatewayMetricsHourly.output_tokens).label("output_tokens"),
            func.sum(GatewayMetricsHourly.cached_tokens).label("cached_tokens"),
            func.sum(GatewayMetricsHourly.cache_creation_tokens).label("cache_creation_tokens"),
            func.sum(GatewayMetricsHourly.cost_usd).label("cost_usd"),
            func.sum(GatewayMetricsHourly.success_count).label("success"),
            func.sum(GatewayMetricsHourly.error_count).label("failure"),
            (latency_weight / func.nullif(success_weight, 0)).label("avg_latency"),
            (ttfb_weight / func.nullif(success_weight, 0)).label("avg_ttfb"),
        ).where(metrics_hourly_and(*clauses))
        row = (await self._session.execute(stmt)).one()
        return {
            "total": int(row.total or 0),
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "cached_tokens": int(row.cached_tokens or 0),
            "cache_creation_tokens": int(row.cache_creation_tokens or 0),
            "cost_usd": Decimal(row.cost_usd or 0),
            "success": int(row.success or 0),
            "failure": int(row.failure or 0),
            "avg_latency_ms": float(row.avg_latency or 0),
            "avg_ttfb_ms": float(row.avg_ttfb or 0),
        }

    async def aggregate_usage_statistics_by_axis(
        self,
        axis: UsageAxis,
        bucket_start: datetime,
        bucket_end_exclusive: datetime,
        *,
        group_by: UsageStatisticsGroupBy,
        filters: UsageStatisticsFilters,
        page: int = 1,
        page_size: int = 20,
        parent_scope: UsageStatisticsParentScope | None = None,
        fetch_all_groups: bool = False,
    ) -> tuple[list[RequestLogUsageAggregateRow], RequestLogUsageTotals, int]:
        group_exprs = self._group_exprs(group_by)
        clauses = [
            *metrics_hourly_axis_clauses(axis),
            *metrics_hourly_time_clauses(bucket_start, bucket_end_exclusive),
            *self._statistics_filter_clauses(filters),
        ]
        if parent_scope is not None:
            clauses.append(self._parent_clause(parent_scope, parent_scope.group_by))

        offset = max(0, (page - 1) * page_size)
        grouped_subq = (
            select(
                group_exprs[0].label("group_key"),
                literal(None).label("label_snapshot"),
                func.sum(GatewayMetricsHourly.requests).label("requests"),
                func.sum(GatewayMetricsHourly.success_count).label("success_count"),
                func.sum(GatewayMetricsHourly.error_count).label("failure_count"),
                func.sum(GatewayMetricsHourly.input_tokens).label("input_tokens"),
                func.sum(GatewayMetricsHourly.output_tokens).label("output_tokens"),
                func.sum(GatewayMetricsHourly.cached_tokens).label("cached_tokens"),
                func.sum(GatewayMetricsHourly.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayMetricsHourly.cost_usd).label("cost_usd"),
                (
                    func.sum(
                        case(
                            (
                                GatewayMetricsHourly.success_count > 0,
                                GatewayMetricsHourly.total_latency_ms,
                            ),
                            else_=0,
                        )
                    )
                    / func.nullif(func.sum(GatewayMetricsHourly.success_count), 0)
                ).label("avg_latency_ms"),
                (
                    func.sum(
                        case(
                            (
                                GatewayMetricsHourly.success_count > 0,
                                GatewayMetricsHourly.ttfb_total_ms,
                            ),
                            else_=0,
                        )
                    )
                    / func.nullif(func.sum(GatewayMetricsHourly.success_count), 0)
                ).label("avg_ttfb_ms"),
                func.sum(GatewayMetricsHourly.cache_hit_count).label("cache_hit_count"),
            )
            .where(metrics_hourly_and(*clauses))
            .group_by(*group_exprs)
            .subquery("hourly_grouped")
        )
        rows_stmt = (
            select(grouped_subq)
            .order_by(grouped_subq.c.requests.desc())
        )
        if not fetch_all_groups:
            rows_stmt = rows_stmt.offset(offset).limit(page_size)
        items: list[RequestLogUsageAggregateRow] = []
        for row in (await self._session.execute(rows_stmt)).all():
            items.append(
                RequestLogUsageAggregateRow(
                    group_key=row.group_key,
                    label_snapshot=row.label_snapshot,
                    requests=int(row.requests or 0),
                    success_count=int(row.success_count or 0),
                    failure_count=int(row.failure_count or 0),
                    input_tokens=int(row.input_tokens or 0),
                    output_tokens=int(row.output_tokens or 0),
                    cached_tokens=int(row.cached_tokens or 0),
                    cache_creation_tokens=int(row.cache_creation_tokens or 0),
                    cost_usd=Decimal(row.cost_usd or 0),
                    avg_latency_ms=float(row.avg_latency_ms or 0),
                    avg_ttfb_ms=float(row.avg_ttfb_ms or 0),
                    cache_hit_count=int(row.cache_hit_count or 0),
                )
            )

        group_total_subq = select(func.count()).select_from(grouped_subq).scalar_subquery()
        totals_stmt = select(
            group_total_subq.label("group_total"),
            func.sum(GatewayMetricsHourly.requests).label("requests"),
            func.sum(GatewayMetricsHourly.success_count).label("success_count"),
            func.sum(GatewayMetricsHourly.error_count).label("failure_count"),
            func.sum(GatewayMetricsHourly.input_tokens).label("input_tokens"),
            func.sum(GatewayMetricsHourly.output_tokens).label("output_tokens"),
            func.sum(GatewayMetricsHourly.cached_tokens).label("cached_tokens"),
            func.sum(GatewayMetricsHourly.cache_creation_tokens).label("cache_creation_tokens"),
            func.sum(GatewayMetricsHourly.cost_usd).label("cost_usd"),
            func.sum(
                case(
                    (GatewayMetricsHourly.success_count > 0, GatewayMetricsHourly.total_latency_ms),
                    else_=0,
                )
            ).label("latency_weight"),
            func.sum(
                case(
                    (GatewayMetricsHourly.success_count > 0, GatewayMetricsHourly.ttfb_total_ms),
                    else_=0,
                )
            ).label("ttfb_weight"),
            func.sum(GatewayMetricsHourly.success_count).label("success_weight"),
            func.sum(GatewayMetricsHourly.cache_hit_count).label("cache_hit_count"),
        ).where(metrics_hourly_and(*clauses))
        total_row = (await self._session.execute(totals_stmt)).one()
        group_total = int(total_row.group_total or 0)
        totals = self._totals_from_row(total_row)
        return items, totals, group_total

    async def count_usage_requests_by_axis(
        self,
        axis: UsageAxis,
        bucket_start: datetime,
        bucket_end_exclusive: datetime,
        *,
        filters: UsageStatisticsFilters,
        parent_scope: UsageStatisticsParentScope | None = None,
    ) -> int:
        clauses = [
            *metrics_hourly_axis_clauses(axis),
            *metrics_hourly_time_clauses(bucket_start, bucket_end_exclusive),
            *self._statistics_filter_clauses(filters),
        ]
        if parent_scope is not None:
            clauses.append(self._parent_clause(parent_scope, parent_scope.group_by))
        stmt = select(func.sum(GatewayMetricsHourly.requests)).where(metrics_hourly_and(*clauses))
        return int((await self._session.execute(stmt)).scalar_one() or 0)

    @staticmethod
    def _totals_from_row(row: object) -> RequestLogUsageTotals:
        success_weight = int(getattr(row, "success_weight", 0) or 0)
        latency_weight = float(getattr(row, "latency_weight", 0) or 0)
        ttfb_weight = float(getattr(row, "ttfb_weight", 0) or 0)
        return RequestLogUsageTotals(
            requests=int(getattr(row, "requests", 0) or 0),
            success_count=int(getattr(row, "success_count", 0) or 0),
            failure_count=int(getattr(row, "failure_count", 0) or 0),
            input_tokens=int(getattr(row, "input_tokens", 0) or 0),
            output_tokens=int(getattr(row, "output_tokens", 0) or 0),
            cached_tokens=int(getattr(row, "cached_tokens", 0) or 0),
            cache_creation_tokens=int(getattr(row, "cache_creation_tokens", 0) or 0),
            cost_usd=Decimal(getattr(row, "cost_usd", 0) or 0),
            avg_latency_ms=latency_weight / success_weight if success_weight > 0 else 0.0,
            avg_ttfb_ms=ttfb_weight / success_weight if success_weight > 0 else 0.0,
            cache_hit_count=int(getattr(row, "cache_hit_count", 0) or 0),
        )

    @staticmethod
    def _parent_in_clause(
        parent_group_by: UsageStatisticsGroupBy,
        parent_keys: list[str],
    ):
        expr = MetricsHourlyReadRepository._group_exprs(parent_group_by)[0]
        keys = [k.strip() for k in parent_keys if k and k.strip()]
        if not keys:
            return literal(False)
        if parent_group_by in (
            UsageStatisticsGroupBy.CREDENTIAL,
            UsageStatisticsGroupBy.USER,
            UsageStatisticsGroupBy.TEAM,
            UsageStatisticsGroupBy.VKEY,
        ):
            from uuid import UUID as _UUID

            return expr.in_([_UUID(k) for k in keys])
        return expr.in_(keys)

    async def aggregate_breakdown_pairs_by_axis(
        self,
        axis: UsageAxis,
        bucket_start: datetime,
        bucket_end_exclusive: datetime,
        *,
        parent_group_by: UsageStatisticsGroupBy,
        breakdown_group_by: UsageStatisticsGroupBy,
        parent_keys: list[str],
        filters: UsageStatisticsFilters,
    ) -> list[BreakdownPairRow]:
        """hourly 冷段：按 ``(父维度, 二次维度)`` 聚合本页所有父行的分布（仅请求数）。"""
        parent_expr = self._group_exprs(parent_group_by)[0]
        breakdown_expr = self._group_exprs(breakdown_group_by)[0]
        clauses = [
            *metrics_hourly_axis_clauses(axis),
            *metrics_hourly_time_clauses(bucket_start, bucket_end_exclusive),
            *self._statistics_filter_clauses(filters),
            self._parent_in_clause(parent_group_by, parent_keys),
        ]
        stmt = (
            select(
                parent_expr.label("parent_key"),
                breakdown_expr.label("breakdown_key"),
                func.sum(GatewayMetricsHourly.requests).label("requests"),
            )
            .where(metrics_hourly_and(*clauses))
            .group_by(parent_expr, breakdown_expr)
        )
        result = await self._session.execute(stmt)
        return [
            BreakdownPairRow(
                parent_key="" if row.parent_key is None else str(row.parent_key),
                breakdown_key=row.breakdown_key,
                label_snapshot=None,
                requests=int(row.requests or 0),
            )
            for row in result.all()
        ]

    @staticmethod
    def _parent_clause(
        parent: UsageStatisticsParentScope,
        group_by: UsageStatisticsGroupBy,
    ):
        key = parent.group_key.strip()
        if group_by == UsageStatisticsGroupBy.MODEL:
            return GatewayMetricsHourly.model_key == key
        if group_by in (
            UsageStatisticsGroupBy.CREDENTIAL,
            UsageStatisticsGroupBy.USER,
            UsageStatisticsGroupBy.TEAM,
            UsageStatisticsGroupBy.VKEY,
        ):
            from uuid import UUID as _UUID

            if not key:
                return MetricsHourlyReadRepository._group_exprs(group_by)[0].is_(None)
            return MetricsHourlyReadRepository._group_exprs(group_by)[0] == _UUID(key)
        if group_by in (
            UsageStatisticsGroupBy.PROVIDER,
            UsageStatisticsGroupBy.CAPABILITY,
        ):
            expr = MetricsHourlyReadRepository._group_exprs(group_by)[0]
            return expr.is_(None) if not key else expr == key
        raise ValueError(f"Unknown parent group_by: {parent.group_by!r}")


__all__ = ["MetricsHourlyReadRepository"]
