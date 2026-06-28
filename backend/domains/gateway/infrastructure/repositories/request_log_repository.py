"""GatewayRequestLogRepository

仓储层基于 ``UsageAxis`` 值对象统一访问 ``gateway_request_logs``，5 对镜像方法（``*_for_team`` /
``*_for_user``）已被 5 个 axis-based 方法取代，SQL 主体只写一次。轴的语义见
``domains.gateway.domain.usage.usage_axis``。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, func, literal, or_, select, true
from sqlalchemy.orm import defer

from domains.gateway.domain.usage.usage_read_model import (
    UsageStatisticsFilters,
    UsageStatisticsGroupBy,
    UsageStatisticsParentScope,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.repositories.usage_axis_sql import (
    usage_axis_base_clauses,
    usage_axis_count_disjuncts,
)

if TYPE_CHECKING:
    from sqlalchemy.sql import ColumnElement


def _sql_and(*clauses: ColumnElement[bool]) -> ColumnElement[bool]:
    """``UsageAxis.platform`` 等场景可能仅有时间窗子句；避免 ``and_()`` 空参数。"""
    if not clauses:
        return true()
    return and_(*clauses)


def _request_log_list_defer_options() -> tuple:
    """列表分页不加载大 JSONB；仅在执行查询时构造，避免 import 阶段触发全量 ORM configure。"""
    return (
        defer(GatewayRequestLog.prompt_redacted),
        defer(GatewayRequestLog.response_summary),
        defer(GatewayRequestLog.metadata_extra),
        defer(GatewayRequestLog.team_snapshot),
        defer(GatewayRequestLog.route_snapshot),
    )


def _success_only_metric(column: Any) -> Any:
    """平均延迟类指标只使用成功请求；失败行返回 NULL 供 avg() 忽略。"""
    return case((GatewayRequestLog.status == "success", column), else_=None)


if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

    from domains.gateway.domain.usage.usage_axis import UsageAxis


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
    cache_creation_tokens: int = 0
    cost_usd: Decimal = Decimal("0")
    avg_latency_ms: float = 0.0
    avg_ttfb_ms: float = 0.0
    cache_hit_count: int = 0


@dataclass(frozen=True)
class BreakdownPairRow:
    """批量 breakdown 的 (父分组键, 二次分组键) 配对聚合行（仅请求数）。"""

    parent_key: str
    breakdown_key: UUID | str | None
    label_snapshot: str | None
    requests: int


@dataclass(frozen=True)
class RequestLogListPage:
    """日志列表分页（probe 模式，无精确 COUNT）。"""

    items: list[GatewayRequestLog]
    has_next: bool


@dataclass(frozen=True)
class RequestLogUsageTotals:
    """调用统计总计。"""

    requests: int
    success_count: int
    failure_count: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cache_creation_tokens: int
    cost_usd: Decimal
    avg_latency_ms: float
    avg_ttfb_ms: float
    cache_hit_count: int


class RequestLogRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    @staticmethod
    def _clause_variants_for_axis(
        axis: UsageAxis,
        clauses: list[ColumnElement[bool]],
    ) -> list[list[ColumnElement[bool]]]:
        """user / workspace-member 轴将可见性 OR 拆成互斥子句，便于走部分索引。"""
        split = usage_axis_count_disjuncts(axis)
        if split is None:
            return [clauses]
        disjuncts, visibility_idx = split
        prefix = clauses[:visibility_idx]
        suffix = clauses[visibility_idx + 1 :]
        return [[*prefix, disjunct, *suffix] for disjunct in disjuncts]

    async def _count_logs(
        self,
        axis: UsageAxis,
        clauses: list[ColumnElement[bool]],
    ) -> int:
        """COUNT 热路径：user / workspace-member 轴拆成两段互斥子查询再相加，便于走部分索引。"""
        total = 0
        for variant in self._clause_variants_for_axis(axis, clauses):
            stmt = select(func.count()).select_from(GatewayRequestLog).where(_sql_and(*variant))
            total += int((await self._session.execute(stmt)).scalar_one())
        return total

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
        cache_creation_tokens: int = 0,
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
        resource_owner_user_id: UUID | None = None,
        client_type: str | None = None,
        client_ua: str | None = None,
        image_count: int = 0,
    ) -> GatewayRequestLog:
        log = GatewayRequestLog(
            tenant_id=team_id,
            user_id=user_id,
            resource_owner_user_id=resource_owner_user_id,
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
            cache_creation_tokens=cache_creation_tokens,
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
            image_count=image_count,
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
        user_id: UUID | None = None,
        model: str | None = None,
        client_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> RequestLogListPage:
        clauses = list(usage_axis_base_clauses(axis))
        if start:
            clauses.append(GatewayRequestLog.created_at >= start)
        if end:
            clauses.append(GatewayRequestLog.created_at <= end)
        clauses.extend(
            self._list_filter_clauses(
                status=status,
                capability=capability,
                vkey_id=vkey_id,
                credential_id=credential_id,
                user_id=user_id,
                model=model,
                client_type=client_type,
            )
        )

        offset = max(0, (page - 1) * page_size)
        probe_limit = page_size + 1
        stmt = (
            select(GatewayRequestLog)
            .options(*_request_log_list_defer_options())
            .where(_sql_and(*clauses))
            .order_by(GatewayRequestLog.created_at.desc())
            .offset(offset)
            .limit(probe_limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        has_next = len(rows) > page_size
        return RequestLogListPage(items=rows[:page_size], has_next=has_next)

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
        stmt = select(GatewayRequestLog).where(_sql_and(*clauses)).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _list_filter_clauses(
        *,
        status: str | None = None,
        capability: str | None = None,
        vkey_id: UUID | None = None,
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
        model: str | None = None,
        client_type: str | None = None,
    ) -> list[ColumnElement[bool]]:
        """构建日志列表/汇总通用的筛选条件子句（与 ``list_by_axis`` 保持一致）。"""
        clauses: list[ColumnElement[bool]] = []
        if status:
            clauses.append(GatewayRequestLog.status == status)
        if capability:
            clauses.append(GatewayRequestLog.capability == capability)
        if vkey_id:
            clauses.append(GatewayRequestLog.vkey_id == vkey_id)
        if credential_id:
            clauses.append(GatewayRequestLog.credential_id == credential_id)
        if user_id:
            clauses.append(GatewayRequestLog.user_id == user_id)
        if model:
            clauses.append(
                or_(
                    GatewayRequestLog.deployment_model_name == model,
                    GatewayRequestLog.route_name == model,
                    GatewayRequestLog.real_model == model,
                )
            )
        if client_type:
            clauses.append(GatewayRequestLog.client_type == client_type)
        return clauses

    async def aggregate_summary_by_axis(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        status: str | None = None,
        capability: str | None = None,
        vkey_id: UUID | None = None,
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
        model: str | None = None,
        client_type: str | None = None,
    ) -> dict[str, Any]:
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            *self._list_filter_clauses(
                status=status,
                capability=capability,
                vkey_id=vkey_id,
                credential_id=credential_id,
                user_id=user_id,
                model=model,
                client_type=client_type,
            ),
        ]
        merged: dict[str, Any] | None = None
        from domains.gateway.application.usage.management.usage_metrics import merge_summary_slices

        for variant in self._clause_variants_for_axis(axis, clauses):
            stmt = select(
                func.count(GatewayRequestLog.id).label("total"),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.sum(case((GatewayRequestLog.status == "success", 1), else_=0)).label(
                    "success"
                ),
                func.sum(case((GatewayRequestLog.status != "success", 1), else_=0)).label(
                    "failure"
                ),
                func.avg(_success_only_metric(GatewayRequestLog.latency_ms)).label("avg_latency"),
                func.avg(_success_only_metric(GatewayRequestLog.ttfb_ms)).label("avg_ttfb"),
            ).where(_sql_and(*variant))
            row = (await self._session.execute(stmt)).one()
            partial = {
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
            merged = partial if merged is None else merge_summary_slices(merged, partial)
        assert merged is not None
        return merged

    async def aggregate_by_client_type(
        self,
        axis: UsageAxis,
        start: datetime,
        end: datetime,
        *,
        status: str | None = None,
        capability: str | None = None,
        vkey_id: UUID | None = None,
        credential_id: UUID | None = None,
        user_id: UUID | None = None,
        model: str | None = None,
        client_type: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            *self._list_filter_clauses(
                status=status,
                capability=capability,
                vkey_id=vkey_id,
                credential_id=credential_id,
                user_id=user_id,
                model=model,
                client_type=client_type,
            ),
        ]
        client_type_expr = func.coalesce(GatewayRequestLog.client_type, "unknown")
        stmt = (
            select(
                client_type_expr.label("client_type"),
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            )
            .where(_sql_and(*clauses))
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
        ).where(_sql_and(*clauses))
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
            .where(_sql_and(*clauses))
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
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            )
            .where(_sql_and(*clauses))
            .group_by(GatewayRequestLog.route_name)
        )
        rows = (await self._session.execute(stmt)).all()
        out: dict[str, dict[str, Any]] = {
            n: {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "cache_creation_tokens": 0,
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
                "cached_tokens": int(row.cached_tokens or 0),
                "cache_creation_tokens": int(row.cache_creation_tokens or 0),
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
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            )
            .where(_sql_and(*clauses))
            .group_by(GatewayRequestLog.deployment_gateway_model_id)
        )
        rows = (await self._session.execute(stmt)).all()
        out: dict[UUID, dict[str, Any]] = {
            mid: {
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "cache_creation_tokens": 0,
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
                "cached_tokens": int(row.cached_tokens or 0),
                "cache_creation_tokens": int(row.cache_creation_tokens or 0),
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
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.sum(case((GatewayRequestLog.status == "success", 1), else_=0)).label(
                    "success"
                ),
                func.sum(case((GatewayRequestLog.status != "success", 1), else_=0)).label(
                    "failure"
                ),
            )
            .where(_sql_and(*clauses))
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
                "cached_tokens": int(row.cached_tokens or 0),
                "cache_creation_tokens": int(row.cache_creation_tokens or 0),
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
        if group_by == UsageStatisticsGroupBy.RESOURCE_OWNER:
            return [GatewayRequestLog.resource_owner_user_id]
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
        return await self._count_logs(axis, clauses)

    @staticmethod
    def _group_key_to_str(value: object) -> str:
        return "" if value is None else str(value)

    @staticmethod
    def _usage_statistics_metric_cases() -> tuple[Any, Any, Any]:
        success_case = case((GatewayRequestLog.status == "success", 1), else_=0)
        failure_case = case((GatewayRequestLog.status != "success", 1), else_=0)
        cache_hit_case = case((GatewayRequestLog.cache_hit.is_(True), 1), else_=0)
        return success_case, failure_case, cache_hit_case

    @classmethod
    def _usage_statistics_group_select(
        cls,
        group_exprs: list[ColumnElement[UUID | str | None]],
        snapshot_exprs: list[ColumnElement[str | None]],
        success_case: Any,
        failure_case: Any,
        cache_hit_case: Any,
    ) -> list[Any]:
        selected: list[Any] = [
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
                func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.avg(_success_only_metric(GatewayRequestLog.latency_ms)).label(
                    "avg_latency_ms"
                ),
                func.avg(_success_only_metric(GatewayRequestLog.ttfb_ms)).label("avg_ttfb_ms"),
                func.sum(cache_hit_case).label("cache_hit_count"),
            ]
        )
        return selected

    def _usage_statistics_row_to_item(
        self,
        row: Any,
        group_exprs: list[ColumnElement[UUID | str | None]],
    ) -> RequestLogUsageAggregateRow:
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
        return RequestLogUsageAggregateRow(
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
            cache_creation_tokens=int(row.cache_creation_tokens or 0),
            cost_usd=Decimal(row.cost_usd or 0),
            avg_latency_ms=float(row.avg_latency_ms or 0),
            avg_ttfb_ms=float(row.avg_ttfb_ms or 0),
            cache_hit_count=int(row.cache_hit_count or 0),
        )

    async def _fetch_usage_statistics_grouped_rows(
        self,
        clauses: list[ColumnElement[bool]],
        *,
        group_exprs: list[ColumnElement[UUID | str | None]],
        snapshot_exprs: list[ColumnElement[str | None]],
        selected: list[Any],
    ) -> list[RequestLogUsageAggregateRow]:
        stmt = (
            select(*selected)
            .where(_sql_and(*clauses))
            .group_by(*group_exprs)
            .order_by(func.count(GatewayRequestLog.id).desc())
        )
        result = await self._session.execute(stmt)
        return [self._usage_statistics_row_to_item(row, group_exprs) for row in result.all()]

    async def _fetch_usage_statistics_totals_dict(
        self,
        clauses: list[ColumnElement[bool]],
        *,
        success_case: Any,
        failure_case: Any,
        cache_hit_case: Any,
    ) -> dict[str, int | float | Decimal]:
        stmt = select(
            func.count(GatewayRequestLog.id).label("requests"),
            func.sum(success_case).label("success_count"),
            func.sum(failure_case).label("failure_count"),
            func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
            func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
            func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
            func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
            func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            func.avg(_success_only_metric(GatewayRequestLog.latency_ms)).label("avg_latency_ms"),
            func.avg(_success_only_metric(GatewayRequestLog.ttfb_ms)).label("avg_ttfb_ms"),
            func.sum(cache_hit_case).label("cache_hit_count"),
        ).where(_sql_and(*clauses))
        row = (await self._session.execute(stmt)).one()
        return {
            "requests": int(row.requests or 0),
            "success_count": int(row.success_count or 0),
            "failure_count": int(row.failure_count or 0),
            "input_tokens": int(row.input_tokens or 0),
            "output_tokens": int(row.output_tokens or 0),
            "cached_tokens": int(row.cached_tokens or 0),
            "cache_creation_tokens": int(row.cache_creation_tokens or 0),
            "cost_usd": Decimal(row.cost_usd or 0),
            "avg_latency_ms": float(row.avg_latency_ms or 0),
            "avg_ttfb_ms": float(row.avg_ttfb_ms or 0),
            "cache_hit_count": int(row.cache_hit_count or 0),
        }

    @staticmethod
    def _usage_statistics_totals_from_dict(
        totals_dict: dict[str, int | float | Decimal],
    ) -> RequestLogUsageTotals:
        cost = totals_dict["cost_usd"]
        return RequestLogUsageTotals(
            requests=int(totals_dict["requests"]),
            success_count=int(totals_dict["success_count"]),
            failure_count=int(totals_dict["failure_count"]),
            input_tokens=int(totals_dict["input_tokens"]),
            output_tokens=int(totals_dict["output_tokens"]),
            cached_tokens=int(totals_dict["cached_tokens"]),
            cache_creation_tokens=int(totals_dict["cache_creation_tokens"]),
            cost_usd=cost if isinstance(cost, Decimal) else Decimal(str(cost or 0)),
            avg_latency_ms=float(totals_dict["avg_latency_ms"]),
            avg_ttfb_ms=float(totals_dict["avg_ttfb_ms"]),
            cache_hit_count=int(totals_dict["cache_hit_count"]),
        )

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
        fetch_all_groups: bool = False,
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
        success_case, failure_case, cache_hit_case = self._usage_statistics_metric_cases()
        selected = self._usage_statistics_group_select(
            group_exprs,
            snapshot_exprs,
            success_case,
            failure_case,
            cache_hit_case,
        )
        clause_variants = self._clause_variants_for_axis(axis, clauses)
        offset = max(0, (page - 1) * page_size)

        if len(clause_variants) == 1:
            variant = clause_variants[0]
            grouped_subq = (
                select(*selected)
                .where(_sql_and(*variant))
                .group_by(*group_exprs)
                .subquery("usage_grouped")
            )
            rows_stmt = select(grouped_subq).order_by(grouped_subq.c.requests.desc())
            if not fetch_all_groups:
                rows_stmt = rows_stmt.offset(offset).limit(page_size)
            result = await self._session.execute(rows_stmt)
            items = [self._usage_statistics_row_to_item(row, group_exprs) for row in result.all()]
            group_total_subq = select(func.count()).select_from(grouped_subq).scalar_subquery()
            totals_stmt = select(
                group_total_subq.label("group_total"),
                func.count(GatewayRequestLog.id).label("requests"),
                func.sum(success_case).label("success_count"),
                func.sum(failure_case).label("failure_count"),
                func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
                func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
                func.sum(GatewayRequestLog.cached_tokens).label("cached_tokens"),
                func.sum(GatewayRequestLog.cache_creation_tokens).label("cache_creation_tokens"),
                func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
                func.avg(_success_only_metric(GatewayRequestLog.latency_ms)).label(
                    "avg_latency_ms"
                ),
                func.avg(_success_only_metric(GatewayRequestLog.ttfb_ms)).label("avg_ttfb_ms"),
                func.sum(cache_hit_case).label("cache_hit_count"),
            ).where(_sql_and(*variant))
            total_row = (await self._session.execute(totals_stmt)).one()
            group_total = int(total_row.group_total or 0)
            totals = RequestLogUsageTotals(
                requests=int(total_row.requests or 0),
                success_count=int(total_row.success_count or 0),
                failure_count=int(total_row.failure_count or 0),
                input_tokens=int(total_row.input_tokens or 0),
                output_tokens=int(total_row.output_tokens or 0),
                cached_tokens=int(total_row.cached_tokens or 0),
                cache_creation_tokens=int(total_row.cache_creation_tokens or 0),
                cost_usd=Decimal(total_row.cost_usd or 0),
                avg_latency_ms=float(total_row.avg_latency_ms or 0),
                avg_ttfb_ms=float(total_row.avg_ttfb_ms or 0),
                cache_hit_count=int(total_row.cache_hit_count or 0),
            )
            return items, totals, group_total

        merged_items: list[RequestLogUsageAggregateRow] = []
        from domains.gateway.application.usage.management.usage_metrics import (
            merge_statistics_items,
            merge_statistics_totals,
        )

        for variant in clause_variants:
            rows = await self._fetch_usage_statistics_grouped_rows(
                variant,
                group_exprs=group_exprs,
                snapshot_exprs=snapshot_exprs,
                selected=selected,
            )
            merged_items = (
                merge_statistics_items(merged_items, rows) if merged_items else list(rows)
            )
        group_total = len(merged_items)
        items = merged_items if fetch_all_groups else merged_items[offset : offset + page_size]

        merged_totals: dict[str, int | float | Decimal] | None = None
        for variant in clause_variants:
            partial = await self._fetch_usage_statistics_totals_dict(
                variant,
                success_case=success_case,
                failure_case=failure_case,
                cache_hit_case=cache_hit_case,
            )
            merged_totals = (
                partial
                if merged_totals is None
                else merge_statistics_totals(merged_totals, partial)
            )
        assert merged_totals is not None
        return items, self._usage_statistics_totals_from_dict(merged_totals), group_total

    @staticmethod
    def _parent_in_clause(
        parent_group_by: UsageStatisticsGroupBy,
        parent_keys: list[str],
    ) -> ColumnElement[bool]:
        """限定到一组父分组键（本页行）；空列表返回恒假以短路。"""
        expr = RequestLogRepository._usage_statistics_group_exprs(parent_group_by)[0]
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
        start: datetime,
        end: datetime,
        *,
        parent_group_by: UsageStatisticsGroupBy,
        breakdown_group_by: UsageStatisticsGroupBy,
        parent_keys: list[str],
        filters: UsageStatisticsFilters,
    ) -> list[BreakdownPairRow]:
        """一次聚合本页所有父行的二次分组分布（仅请求数），供批量 breakdown。

        按 ``(父维度, 二次维度)`` 双重分组；``NULL`` 二次键（未关联）保留为独立分桶，
        使某父键的全部分桶请求数之和即为该父键总请求数，免去额外 count 查询。
        """
        parent_expr = self._usage_statistics_group_exprs(parent_group_by)[0]
        breakdown_expr = self._usage_statistics_group_exprs(breakdown_group_by)[0]
        breakdown_snapshot = self._usage_statistics_snapshot_exprs(breakdown_group_by)[0]
        clauses = [
            *usage_axis_base_clauses(axis),
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
            *self._usage_statistics_filter_clauses(filters),
            self._parent_in_clause(parent_group_by, parent_keys),
        ]
        stmt = (
            select(
                parent_expr.label("parent_key"),
                breakdown_expr.label("breakdown_key"),
                breakdown_snapshot.label("label_snapshot"),
                func.count(GatewayRequestLog.id).label("requests"),
            )
            .where(_sql_and(*clauses))
            .group_by(parent_expr, breakdown_expr)
        )
        result = await self._session.execute(stmt)
        return [
            BreakdownPairRow(
                parent_key=self._group_key_to_str(row.parent_key),
                breakdown_key=row.breakdown_key,
                label_snapshot=row.label_snapshot,
                requests=int(row.requests or 0),
            )
            for row in result.all()
        ]


__all__ = [
    "BreakdownPairRow",
    "RequestLogListPage",
    "RequestLogRepository",
    "RequestLogUsageAggregateRow",
    "RequestLogUsageTotals",
]
