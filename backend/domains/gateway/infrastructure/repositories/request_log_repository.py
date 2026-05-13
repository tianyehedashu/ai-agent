"""GatewayRequestLogRepository"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, func, select

from domains.gateway.infrastructure.models.request_log import GatewayRequestLog

if TYPE_CHECKING:
    from datetime import datetime
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class RequestLogRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert(
        self,
        *,
        team_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
        vkey_id: uuid.UUID | None,
        team_snapshot: dict[str, Any] | None,
        user_email_snapshot: str | None,
        vkey_name_snapshot: str | None,
        route_snapshot: dict[str, Any] | None,
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
        latency_ms: int,
        ttfb_ms: int | None,
        cache_hit: bool,
        fallback_chain: list[str],
        request_id: str | None,
        prompt_hash: str | None,
        prompt_redacted: dict[str, Any] | None,
        response_summary: dict[str, Any] | None,
        metadata_extra: dict[str, Any] | None,
    ) -> GatewayRequestLog:
        log = GatewayRequestLog(
            team_id=team_id,
            user_id=user_id,
            vkey_id=vkey_id,
            team_snapshot=team_snapshot,
            user_email_snapshot=user_email_snapshot,
            vkey_name_snapshot=vkey_name_snapshot,
            route_snapshot=route_snapshot,
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
            latency_ms=latency_ms,
            ttfb_ms=ttfb_ms,
            cache_hit=cache_hit,
            fallback_chain=fallback_chain,
            request_id=request_id,
            prompt_hash=prompt_hash,
            prompt_redacted=prompt_redacted,
            response_summary=response_summary,
            metadata_extra=metadata_extra,
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_for_team(
        self,
        team_id: uuid.UUID,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
        capability: str | None = None,
        vkey_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GatewayRequestLog], int]:
        clauses = [GatewayRequestLog.team_id == team_id]
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

        count_stmt = select(func.count()).select_from(GatewayRequestLog).where(
            and_(*clauses)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        offset = max(0, (page - 1) * page_size)
        stmt = (
            select(GatewayRequestLog)
            .where(and_(*clauses))
            .order_by(GatewayRequestLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        status: str | None = None,
        capability: str | None = None,
        vkey_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[GatewayRequestLog], int]:
        clauses = [GatewayRequestLog.user_id == user_id]
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

        count_stmt = select(func.count()).select_from(GatewayRequestLog).where(
            and_(*clauses)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()

        offset = max(0, (page - 1) * page_size)
        stmt = (
            select(GatewayRequestLog)
            .where(and_(*clauses))
            .order_by(GatewayRequestLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_for_team(
        self,
        log_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> GatewayRequestLog | None:
        """按 ID 读取日志，且必须属于指定团队"""
        # 分区表主键为 (id, created_at)，不可用 session.get 单单传入 id
        stmt = (
            select(GatewayRequestLog)
            .where(
                GatewayRequestLog.id == log_id,
                GatewayRequestLog.team_id == team_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_user(
        self,
        log_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> GatewayRequestLog | None:
        """按 ID 读取日志，且必须归属于指定用户"""
        stmt = (
            select(GatewayRequestLog)
            .where(
                GatewayRequestLog.id == log_id,
                GatewayRequestLog.user_id == user_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def aggregate_summary(
        self,
        team_id: uuid.UUID | None,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        clauses = [
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
        ]
        if team_id is not None:
            clauses.append(GatewayRequestLog.team_id == team_id)

        stmt = select(
            func.count(GatewayRequestLog.id).label("total"),
            func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
            func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
            func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            func.sum(
                case((GatewayRequestLog.status == "success", 1), else_=0)
            ).label("success"),
            func.sum(
                case((GatewayRequestLog.status != "success", 1), else_=0)
            ).label("failure"),
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

    async def aggregate_summary_for_user(
        self,
        user_id: uuid.UUID,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        clauses = [
            GatewayRequestLog.user_id == user_id,
            GatewayRequestLog.created_at >= start,
            GatewayRequestLog.created_at <= end,
        ]

        stmt = select(
            func.count(GatewayRequestLog.id).label("total"),
            func.sum(GatewayRequestLog.input_tokens).label("input_tokens"),
            func.sum(GatewayRequestLog.output_tokens).label("output_tokens"),
            func.sum(GatewayRequestLog.cost_usd).label("cost_usd"),
            func.sum(
                case((GatewayRequestLog.status == "success", 1), else_=0)
            ).label("success"),
            func.sum(
                case((GatewayRequestLog.status != "success", 1), else_=0)
            ).label("failure"),
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


__all__ = ["RequestLogRepository"]
