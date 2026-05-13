"""兼容层用量只读查询（供 identity 路由等调用，不暴露 ORM）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.tenancy.infrastructure.models.team import Team


@dataclass(frozen=True)
class UserQuotaReadModel:
    """用户维度配额快照（兼容旧 /usage/quota 字段）。"""

    user_id: UUID
    daily_text_requests: int | None
    monthly_token_limit: int | None
    current_daily_text: int
    current_monthly_tokens: int
    daily_reset_at: datetime | None
    monthly_reset_at: datetime | None


@dataclass(frozen=True)
class UsageLogReadModel:
    """单条用量日志只读视图。"""

    id: UUID
    capability: str
    provider: str
    model: str | None
    key_source: str
    input_tokens: int | None
    output_tokens: int | None
    image_count: int | None
    cost_estimate: Decimal | None
    created_at: datetime


class GatewayUsageReadService:
    """从 Gateway 表读取用量与配额；调用方不 import ORM。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_quota_snapshot(self, user_id: UUID) -> UserQuotaReadModel | None:
        daily = (
            await self._session.execute(
                select(GatewayBudget).where(
                    GatewayBudget.scope == "user",
                    GatewayBudget.scope_id == user_id,
                    GatewayBudget.period == "daily",
                )
            )
        ).scalar_one_or_none()
        monthly = (
            await self._session.execute(
                select(GatewayBudget).where(
                    GatewayBudget.scope == "user",
                    GatewayBudget.scope_id == user_id,
                    GatewayBudget.period == "monthly",
                )
            )
        ).scalar_one_or_none()

        if daily is None and monthly is None:
            return None

        return UserQuotaReadModel(
            user_id=user_id,
            daily_text_requests=daily.limit_requests if daily else None,
            monthly_token_limit=monthly.limit_tokens if monthly else None,
            current_daily_text=daily.current_requests if daily else 0,
            current_monthly_tokens=monthly.current_tokens if monthly else 0,
            daily_reset_at=daily.reset_at if daily else None,
            monthly_reset_at=monthly.reset_at if monthly else None,
        )

    async def list_recent_usage_logs_for_user(
        self,
        user_id: UUID,
        *,
        limit: int,
        offset: int,
        window_days: int = 90,
    ) -> list[UsageLogReadModel]:
        since = datetime.now(UTC) - timedelta(days=window_days)
        team_ids_subq = select(Team.id).where(Team.owner_user_id == user_id)
        stmt = (
            select(GatewayRequestLog)
            .where(
                (GatewayRequestLog.user_id == user_id)
                | (GatewayRequestLog.team_id.in_(team_ids_subq))
            )
            .where(GatewayRequestLog.created_at >= since)
            .order_by(GatewayRequestLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        logs = list(result.scalars().all())
        return [
            UsageLogReadModel(
                id=log.id,
                capability=log.capability,
                provider=log.provider or "unknown",
                model=log.real_model,
                key_source="vkey" if log.vkey_id else "system",
                input_tokens=log.input_tokens,
                output_tokens=log.output_tokens,
                image_count=None,
                cost_estimate=log.cost_usd,
                created_at=log.created_at,
            )
            for log in logs
        ]


__all__ = [
    "GatewayUsageReadService",
    "UsageLogReadModel",
    "UserQuotaReadModel",
]
