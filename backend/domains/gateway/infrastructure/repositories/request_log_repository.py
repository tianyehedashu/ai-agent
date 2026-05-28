"""GatewayRequestLogRepository

仓储层基于 ``UsageAxis`` 值对象统一访问 ``gateway_request_logs``，5 对镜像方法（``*_for_team`` /
``*_for_user``）已被 5 个 axis-based 方法取代，SQL 主体只写一次。轴的语义见
``domains.gateway.domain.usage_axis``。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, func, literal, or_, select
from sqlalchemy.orm import defer

from domains.gateway.domain.usage_read_model import (
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
    UsageStatisticsParentScope,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.repositories.usage_axis_sql import usage_axis_base_clauses


def _request_log_list_defer_options() -> tuple:
    """列表分页不加载大 JSONB；仅在执行查询时构造，避免 import 阶段触发全量 ORM configure。"""
    return (
        defer(GatewayRequestLog.prompt_redacted),
        defer(GatewayRequestLog.response_summary),
        defer(GatewayRequestLog.metadata_extra),
        defer(GatewayRequestLog.team_snapshot),
        defer(GatewayRequestLog.route_snapshot),
    )


if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

    from domains.gateway.domain.usage_axis import UsageAxis


@dataclass(frozen=True)
class RequestLogUsageAggregateRow:
    """一组调用统计聚合结果。"""

    group_key: UUID | str | None
    label_snapshot: str | None
    group_key_parts: list[str] | None = None
    label_parts: list[str] | None = None
    requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    avg_latency_ms: float = 0.0
    cache_hit_count: int = 0


@dataclass(frozen=True)
class RequestLogUsageTotals:
    """调用统计总计。"""

    requests: int
    success_count: int
    failure_count: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: Decimal
    avg_latency_ms: float
    cache_hit_count: int


class RequestLogRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert(
        self,
        *,
        team_id: UUID | None,
        user_id: UUID | None,
        vkey_id: UUID | None,
        team_snapshot: dict[str, Any] | None,
        user_email_snapshot: str | None,
        vkey_name_snapshot: str | None,
        route_snapshot: dict[str, Any] | None,
        credential_id: UUID | None,
        credential_name_snapshot: str | None,
        deployment_gateway_model_id: UUID | None,
        deployment_model_name: str | None,
        capability: str,
        route_name: str | None,
        real_model: str | None,
        provider: str | None,
        status: str,
        error_code: str | None,
        error_message: str | None,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        cost_usd: Decimal,
        revenue_usd: Decimal | None = None,
        pricing_snapshot: dict[str, Any] | None = None,
        latency_ms: int,
        ttfb_ms: int | None,
        cache_hit: bool,
        fallback_chain: list[str],
        request_id: str | None,
        prompt_hash: str | None,
        prompt_redacted: dict[str, Any] | None,
        response_summary: dict[str, Any] | None,
        metadata_extra: dict[str, Any] | None,
        entitlement_plan_id: UUID | None = None,
        provider_plan_id: UUID | None = None,
        client_type: str | None = None,
        client_ua: str | None = None,
    ) -> GatewayRequestLog:
        log = GatewayRequestLog(
            tenant_id=team_id,
            user_id=user_id,
            vkey_id=vkey_id,
            team_snapshot=team_snapshot,
            user_email_snapshot=user_email_snapshot,
            vkey_name_snapshot=vkey_name_snapshot,
            route_snapshot=route_snapshot,
            credential_id=credential_id,
            credential_name_snapshot=credential_name_snapshot,
            entitlement_plan_id=entitlement_plan_id,
            provider_plan_id=provider_plan_id,
            deployment_gateway_model_id=deployment_gateway_model_id,
            deployment_model_name=deployment_model_name,
            capability=capability,
            route_name=route_name,
            real_model=real_model,
            provider=provider,
            status=status,
            error_code=error_code,
            error_message=error_message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            cost_usd=cost_usd,
            revenue_usd=revenue_usd if revenue_usd is not None else cost_usd,
            pricing_snapshot=pricing_snapshot,
            latency_ms=latency_ms,
            ttfb_ms=ttfb_ms,
            cache_hit=cache_hit,
            fallback_chain=fallback_chain,
            request_id=request_id,
            prompt_hash=prompt_hash,
            prompt_redacted=prompt_redacted,
            response_summary=response_summary,
            metadata_extra=metadata_extra,
            client_type=client_type,
            client_ua=client_ua,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_by_axis(
        self,
        axis: UsageAxis,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
        capability: str | None = None,
        vkey_id: UUID | None = None,
        credential_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GatewayRequestLog], int]:
        clauses = list(usage_axis_base_clauses(axis))
        if start:
            clauses.append(GatewayRequestLog.created_at >= start)
        if end:
            clauses.append(GatewayRequestLog.created_at <= end)
        if status:
            clauses.append(GatewayRequestLog.status == status)
        if capability:
            clauses.append(GatewayRequestLog.capability == capability)
        if vkey_id:
            clauses.append(GatewayRequestLog.vkey_id == vkey_id)
        if credential_id:
            clauses.append(GatewayRequestLog.credential_id == credential_id)

        count_stmt = select(func.count()).select_from(GatewayRequestLog).where(and_(*clauses))
        total = (await self._session.execute(count_stmt)).scalar_one()

        offset = max(0, (page - 1) * page_size)
        stmt = (
            select(GatewayRequestLog)
            .options(*_request_log_list_defer_options())
            .where(and_(*clauses))
            .order_by(GatewayRequestLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_axis(
        self,
        axis: UsageAxis,
        log_id: UUID,
    ) -> GatewayRequestLog | None:
        """按 ID 读取日志，且必须满足 axis 基础约束。

        与 ``list_by_axis`` / ``aggregate_*_by_axis`` 对称，统一经 ``usage_axis_base_clauses``
        生成 WHERE 子句。注意 ``UsageAxis.workspace.member_user_id`` 子约束会让单条查询
        在分区表上引入 EXISTS 子查询，对 partition pruning 略不友好；调用方（应用层
        ``get_request_log``）习惯传入未携带 ``member_user_id`` 的 axis，由应用层自行处理
        团队成员可见性，以便区分 ``NotFound`` 与 ``PermissionDenied``。
        """
        # 分区表主键为 (id, created_at)，不可用 session.get 单单传入 id
        clauses = [*usage_axis_base_clauses(axis), GatewayRequestLog.id == log_id]
        stmt = select(GatewayRequestLog).where(and_(*clauses)).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def aggregate_summary_by_axis(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
        ]
        stmt = select(
            func.count(GatewayRequestLog.id).label("total"),
            func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
            func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
            func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            func.sum(case((GatewayRequestLog.status == "success", 1), else_=0)).label("success"),
            func.sum(case((GatewayRequestLog.status != "success", 1), else_=0)).label("failure"),
            func.avg(GatewayRequestLog.latency_ms).label("avg_latency"),
        ).where(and_(*clauses))
        row = (await self._session.execute(stmt)).one()
        return {
            "total": int(row.total or 0),
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "cost_usd": Decimal(row.cost_usd or 0),
            "success": int(row.success or 0),
            "failure": int(row.failure or 0),
            "avg_latency_ms": float(row.avg_latency or 0),
        }

    async def aggregate_by_client_type(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
        ]
        client_type_expr = func.coalesce(GatewayRequestLog.client_type, "unknown")
        stmt = (
            select(
                client_type_expr.label("client_type"),
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            )
            .where(and_(*clauses))
            .group_by(client_type_expr)
            .order_by(func.count(GatewayRequestLog.id).desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            {
                "client_type": str(row.client_type),
                "requests": int(row.requests or 0),
                "cost_usd": Decimal(row.cost_usd or 0),
            }
            for row in rows
        ]

    async def aggregate_billing_summary_by_axis(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
        ]
        stmt = select(
            func.count(GatewayRequestLog.id).label("requests"),
            func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            func.sum(GatewayRequestLog.revenue_usd).label("revenue_usd"),
        ).where(and_(*clauses))
        row = (await self._session.execute(stmt)).one()
        cost = Decimal(row.cost_usd or 0)
        revenue = Decimal(row.revenue_usd or 0)
        return {
            "requests": int(row.requests or 0),
            "cost_usd": cost,
            "revenue_usd": revenue,
            "margin_usd": revenue - cost,
        }

    async def aggregate_top_routes_billing_by_axis(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
        ]
        stmt = (
            select(
                GatewayRequestLog.route_name,
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.sum(GatewayRequestLog.revenue_usd).label("revenue_usd"),
            )
            .where(and_(*clauses))
            .group_by(GatewayRequestLog.route_name)
            .order_by(func.sum(GatewayRequestLog.revenue_usd).desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        out: list[dict[str, Any]] = []
        for r in rows:
            cost = Decimal(r.cost_usd or 0)
            revenue = Decimal(r.revenue_usd or 0)
            out.append(
                {
                    "route_name": r.route_name,
                    "requests": int(r.requests or 0),
                    "cost_usd": cost,
                    "revenue_usd": revenue,
                    "margin_usd": revenue - cost,
                }
            )
        return out

    async def aggregate_by_route_names_by_axis(
        self,
        axis: UsageAxis,
        route_names: list[str],
        start: datetime,
        end: datetime,
    ) -> dict[str, dict[str, Any]]:
        """按 ``route_name`` 聚合；**仅** ``deployment_gateway_model_id`` 为空的行（直连或未解析 deployment 的历史数据）。"""
        if not route_names:
            return {}
        uniq = list(dict.fromkeys(route_names))[:500]
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            GatewayRequestLog.route_name.in_(uniq),
            GatewayRequestLog.deployment_gateway_model_id.is_(None),
        ]
        stmt = (
            select(
                GatewayRequestLog.route_name,
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            )
            .where(and_(*clauses))
            .group_by(GatewayRequestLog.route_name)
        )
        rows = (await self._session.execute(stmt)).all()
        out: dict[str, dict[str, Any]] = {
            n: {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": Decimal("0"),
            }
            for n in uniq
        }
        for row in rows:
            key = row.route_name
            if key is None:
                continue
            out[str(key)] = {
                "requests": int(row.requests or 0),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "cost_usd": Decimal(row.cost_usd or 0),
            }
        return out

    async def aggregate_by_deployment_ids_by_axis(
        self,
        axis: UsageAxis,
        model_ids: list[UUID],
        start: datetime,
        end: datetime,
    ) -> dict[UUID, dict[str, Any]]:
        """按 ``deployment_gateway_model_id``（Router 选中的注册模型）聚合用量。"""
        if not model_ids:
            return {}
        uniq = list(dict.fromkeys(model_ids))[:500]
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            GatewayRequestLog.deployment_gateway_model_id.in_(uniq),
        ]
        stmt = (
            select(
                GatewayRequestLog.deployment_gateway_model_id,
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            )
            .where(and_(*clauses))
            .group_by(GatewayRequestLog.deployment_gateway_model_id)
        )
        rows = (await self._session.execute(stmt)).all()
        out: dict[UUID, dict[str, Any]] = {
            mid: {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": Decimal("0"),
            }
            for mid in uniq
        }
        for row in rows:
            key = row.deployment_gateway_model_id
            if key is None:
                continue
            out[key] = {
                "requests": int(row.requests or 0),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "cost_usd": Decimal(row.cost_usd or 0),
            }
        return out

    async def aggregate_by_credential_global(
        self,
        start: datetime,
        end: datetime,
    ) -> dict[UUID, dict[str, Any]]:
        """全平台按凭据聚合（仅 ``credential_id`` 非空）；供平台管理员只读统计。

        与 ``UsageAxis`` 维度互斥：本方法跨所有租户聚合，不接受 axis 参数。
        """
        clauses = [
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            GatewayRequestLog.credential_id.isnot(None),
        ]
        stmt = (
            select(
                GatewayRequestLog.credential_id,
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.sum(case((GatewayRequestLog.status == "success", 1), else_=0)).label(
                    "success"
                ),
                func.sum(case((GatewayRequestLog.status != "success", 1), else_=0)).label(
                    "failure"
                ),
            )
            .where(and_(*clauses))
            .group_by(GatewayRequestLog.credential_id)
        )
        rows = (await self._session.execute(stmt)).all()
        out: dict[UUID, dict[str, Any]] = {}
        for row in rows:
            cid = row.credential_id
            if cid is None:
                continue
            out[cid] = {
                "requests": int(row.requests or 0),
                "input_tokens": int(row.input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "cost_usd": Decimal(row.cost_usd or 0),
                "success": int(row.success or 0),
                "failure": int(row.failure or 0),
            }
        return out

    @staticmethod
    def _usage_statistics_group_exprs(
        group_by: UsageStatisticsGroupBy,
    ) -> list[ColumnElement[UUID | str | None]]:
        if group_by == UsageStatisticsGroupBy.CREDENTIAL:
            return [GatewayRequestLog.credential_id]
        if group_by == UsageStatisticsGroupBy.USER:
            return [GatewayRequestLog.user_id]
        if group_by == UsageStatisticsGroupBy.TEAM:
            return [GatewayRequestLog.tenant_id]
        if group_by == UsageStatisticsGroupBy.MODEL:
            return [
                func.coalesce(
                    GatewayRequestLog.deployment_model_name,
                    GatewayRequestLog.route_name,
                    GatewayRequestLog.real_model,
                )
            ]
        if group_by == UsageStatisticsGroupBy.VKEY:
            return [GatewayRequestLog.vkey_id]
        if group_by == UsageStatisticsGroupBy.PROVIDER:
            return [GatewayRequestLog.provider]
        if group_by == UsageStatisticsGroupBy.CAPABILITY:
            return [GatewayRequestLog.capability]
        if group_by == UsageStatisticsGroupBy.STATUS:
            return [GatewayRequestLog.status]
        if group_by == UsageStatisticsGroupBy.USER_MODEL_CREDENTIAL:
            return [
                GatewayRequestLog.user_id,
                func.coalesce(
                    GatewayRequestLog.deployment_model_name,
                    GatewayRequestLog.route_name,
                    GatewayRequestLog.real_model,
                ),
                GatewayRequestLog.credential_id,
            ]
        raise ValueError(f"Unknown usage statistics group_by: {group_by!r}")

    @staticmethod
    def _usage_statistics_snapshot_exprs(
        group_by: UsageStatisticsGroupBy,
    ) -> list[ColumnElement[str | None]]:
        if group_by == UsageStatisticsGroupBy.CREDENTIAL:
            return [func.max(GatewayRequestLog.credential_name_snapshot)]
        if group_by == UsageStatisticsGroupBy.USER:
            return [func.max(GatewayRequestLog.user_email_snapshot)]
        if group_by == UsageStatisticsGroupBy.VKEY:
            return [func.max(GatewayRequestLog.vkey_name_snapshot)]
        if group_by == UsageStatisticsGroupBy.USER_MODEL_CREDENTIAL:
            return [
                func.max(GatewayRequestLog.user_email_snapshot),
                literal(None),
                func.max(GatewayRequestLog.credential_name_snapshot),
            ]
        return [literal(None)]

    @staticmethod
    def _usage_statistics_filter_clauses(
        filters: UsageStatisticsFilters,
    ) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = []
        if filters.credential_id is not None:
            clauses.append(GatewayRequestLog.credential_id == filters.credential_id)
        if filters.user_id is not None:
            clauses.append(GatewayRequestLog.user_id == filters.user_id)
        if filters.team_id is not None:
            clauses.append(GatewayRequestLog.tenant_id == filters.team_id)
        if filters.vkey_id is not None:
            clauses.append(GatewayRequestLog.vkey_id == filters.vkey_id)
        if filters.model is not None:
            clauses.append(
                or_(
                    GatewayRequestLog.deployment_model_name == filters.model,
                    GatewayRequestLog.route_name == filters.model,
                    GatewayRequestLog.real_model == filters.model,
                )
            )
        if filters.provider is not None:
            clauses.append(GatewayRequestLog.provider == filters.provider)
        if filters.capability is not None:
            clauses.append(GatewayRequestLog.capability == filters.capability)
        if filters.status is not None:
            clauses.append(GatewayRequestLog.status == filters.status)
        return clauses

    @staticmethod
    def _usage_statistics_parent_clause(
        parent: UsageStatisticsParentScope,
    ) -> ColumnElement[bool]:
        group_expr = RequestLogRepository._usage_statistics_group_exprs(parent.group_by)[0]
        key = parent.group_key.strip()
        if not key:
            return group_expr.is_(None)
        if parent.group_by in (
            UsageStatisticsGroupBy.CREDENTIAL,
            UsageStatisticsGroupBy.USER,
            UsageStatisticsGroupBy.TEAM,
            UsageStatisticsGroupBy.VKEY,
        ):
            from uuid import UUID as _UUID

            return group_expr == _UUID(key)
        if parent.group_by == UsageStatisticsGroupBy.MODEL:
            return or_(
                GatewayRequestLog.deployment_model_name == key,
                GatewayRequestLog.route_name == key,
                GatewayRequestLog.real_model == key,
            )
        if parent.group_by in (
            UsageStatisticsGroupBy.PROVIDER,
            UsageStatisticsGroupBy.CAPABILITY,
            UsageStatisticsGroupBy.STATUS,
        ):
            return group_expr == key
        if parent.group_by == UsageStatisticsGroupBy.USER_MODEL_CREDENTIAL:
            raise ValueError("breakdown is not supported for user_model_credential grouping")
        raise ValueError(f"Unknown parent group_by: {parent.group_by!r}")

    async def count_usage_requests_by_axis(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        filters: UsageStatisticsFilters,
        parent_scope: UsageStatisticsParentScope | None = None,
    ) -> int:
        """统计时间窗内满足过滤（及可选父行范围）的请求条数。"""
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            *self._usage_statistics_filter_clauses(filters),
        ]
        if parent_scope is not None:
            clauses.append(self._usage_statistics_parent_clause(parent_scope))
        stmt = select(func.count(GatewayRequestLog.id)).where(and_(*clauses))
        return int((await self._session.execute(stmt)).scalar_one())

    @staticmethod
    def _group_key_to_str(value: object) -> str:
        return "" if value is None else str(value)

    async def aggregate_usage_statistics_by_axis(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        group_by: UsageStatisticsGroupBy,
        filters: UsageStatisticsFilters,
        page: int = 1,
        page_size: int = 20,
        parent_scope: UsageStatisticsParentScope | None = None,
    ) -> tuple[list[RequestLogUsageAggregateRow], RequestLogUsageTotals, int]:
        """按指定维度聚合调用统计，并返回同一过滤条件下的总计与分组总数。"""
        group_exprs = self._usage_statistics_group_exprs(group_by)
        snapshot_exprs = self._usage_statistics_snapshot_exprs(group_by)
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            *self._usage_statistics_filter_clauses(filters),
        ]
        if parent_scope is not None:
            clauses.append(self._usage_statistics_parent_clause(parent_scope))
        success_case = case((GatewayRequestLog.status == "success", 1), else_=0)
        failure_case = case((GatewayRequestLog.status != "success", 1), else_=0)
        cache_hit_case = case((GatewayRequestLog.cache_hit.is_(True), 1), else_=0)

        group_subq = (
            select(*[expr.label(f"gk_{i}") for i, expr in enumerate(group_exprs)])
            .where(and_(*clauses))
            .group_by(*group_exprs)
            .subquery()
        )
        group_total = int(
            (await self._session.execute(select(func.count()).select_from(group_subq))).scalar_one()
        )

        offset = max(0, (page - 1) * page_size)
        selected = [
            group_exprs[0].label("group_key"),
            snapshot_exprs[0].label("label_snapshot"),
        ]
        for i, expr in enumerate(group_exprs[1:], 1):
            selected.append(expr.label(f"gk_{i}"))
        for i, expr in enumerate(snapshot_exprs[1:], 1):
            selected.append(expr.label(f"ls_{i}"))
        selected.extend(
            [
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(success_case).label("success_count"),
                func.sum(failure_case).label("failure_count"),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.avg(GatewayRequestLog.latency_ms).label("avg_latency_ms"),
                func.sum(cache_hit_case).label("cache_hit_count"),
            ]
        )
        rows_stmt = (
            select(*selected)
            .where(and_(*clauses))
            .group_by(*group_exprs)
            .order_by(func.count(GatewayRequestLog.id).desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self._session.execute(rows_stmt)
        items: list[RequestLogUsageAggregateRow] = []
        for row in result.all():
            group_key_parts: list[str] | None = None
            label_parts: list[str] | None = None
            if len(group_exprs) > 1:
                group_key_parts = [self._group_key_to_str(row.group_key)]
                label_parts = [row.label_snapshot or ""]
                for i in range(1, len(group_exprs)):
                    gk = getattr(row, f"gk_{i}")
                    ls = getattr(row, f"ls_{i}")
                    group_key_parts.append(self._group_key_to_str(gk))
                    label_parts.append(ls or "")
            items.append(
                RequestLogUsageAggregateRow(
                    group_key=row.group_key,
                    label_snapshot=row.label_snapshot,
                    group_key_parts=group_key_parts,
                    label_parts=label_parts,
                    requests=int(row.requests or 0),
                    success_count=int(row.success_count or 0),
                    failure_count=int(row.failure_count or 0),
                    input_tokens=int(row.input_tokens or 0),
                    output_tokens=int(row.output_tokens or 0),
                    cached_tokens=int(row.cached_tokens or 0),
                    cost_usd=Decimal(row.cost_usd or 0),
                    avg_latency_ms=float(row.avg_latency_ms or 0),
                    cache_hit_count=int(row.cache_hit_count or 0),
                )
            )

        totals_stmt = select(
            func.count(GatewayRequestLog.id).label("requests"),
            func.sum(success_case).label("success_count"),
            func.sum(failure_case).label("failure_count"),
            func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
            func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
            func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
            func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            func.avg(GatewayRequestLog.latency_ms).label("avg_latency_ms"),
            func.sum(cache_hit_case).label("cache_hit_count"),
        ).where(and_(*clauses))
        total_row = (await self._session.execute(totals_stmt)).one()
        totals = RequestLogUsageTotals(
            requests=int(total_row.requests or 0),
            success_count=int(total_row.success_count or 0),
            failure_count=int(total_row.failure_count or 0),
            input_tokens=int(total_row.input_tokens or 0),
            output_tokens=int(total_row.output_tokens or 0),
            cached_tokens=int(total_row.cached_tokens or 0),
            cost_usd=Decimal(total_row.cost_usd or 0),
            avg_latency_ms=float(total_row.avg_latency_ms or 0),
            cache_hit_count=int(total_row.cache_hit_count or 0),
        )
        return items, totals, group_total


__all__ = [
    "RequestLogRepository",
    "RequestLogUsageAggregateRow",
    "RequestLogUsageTotals",
]
