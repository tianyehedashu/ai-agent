"""GatewayRequestLogRepository

仓储层基于 ``UsageAxis`` 值对象统一访问 ``gateway_request_logs``，5 对镜像方法（``*_for_team`` /
``*_for_user``）已被 5 个 axis-based 方法取代，SQL 主体只写一次。轴的语义见
``domains.gateway.domain.usage_axis``。
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import defer

from domains.gateway.infrastructure.models.request_log import GatewayRequestLog


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

    from domains.gateway.domain.usage_axis import UsageAxis


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
        clauses = list(axis.base_clauses())
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

        与 ``list_by_axis`` / ``aggregate_*_by_axis`` 对称，统一经 ``axis.base_clauses()``
        生成 WHERE 子句。注意 ``UsageAxis.workspace.member_user_id`` 子约束会让单条查询
        在分区表上引入 EXISTS 子查询，对 partition pruning 略不友好；调用方（应用层
        ``get_request_log``）习惯传入未携带 ``member_user_id`` 的 axis，由应用层自行处理
        团队成员可见性，以便区分 ``NotFound`` 与 ``PermissionDenied``。
        """
        # 分区表主键为 (id, created_at)，不可用 session.get 单单传入 id
        clauses = [*axis.base_clauses(), GatewayRequestLog.id == log_id]
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
            *axis.base_clauses(),
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
            *axis.base_clauses(),
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
            *axis.base_clauses(),
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
            *axis.base_clauses(),
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
            *axis.base_clauses(),
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
            *axis.base_clauses(),
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


__all__ = ["RequestLogRepository"]
