"""GatewayBudgetRepository"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import and_, select, update

from domains.gateway.infrastructure.models.budget import GatewayBudget

if TYPE_CHECKING:
    from datetime import datetime
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class BudgetRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, budget_id: uuid.UUID) -> GatewayBudget | None:
        return await self._session.get(GatewayBudget, budget_id)

    async def list_for_scope(self, scope: str, scope_id: uuid.UUID | None) -> list[GatewayBudget]:
        stmt = select(GatewayBudget).where(
            and_(GatewayBudget.scope == scope, GatewayBudget.scope_id == scope_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_for(
        self,
        scope: str,
        scope_id: uuid.UUID | None,
        period: str,
        *,
        model_name: str | None = None,
    ) -> GatewayBudget | None:
        if model_name is None:
            model_clause = GatewayBudget.model_name.is_(None)
        else:
            model_clause = GatewayBudget.model_name == model_name
        stmt = select(GatewayBudget).where(
            and_(
                GatewayBudget.scope == scope,
                GatewayBudget.scope_id == scope_id,
                GatewayBudget.period == period,
                model_clause,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        period: str,
        model_name: str | None = None,
        limit_usd: Decimal | None = None,
        limit_tokens: int | None = None,
        limit_requests: int | None = None,
        reset_at: datetime | None = None,
    ) -> GatewayBudget:
        existing = await self.get_for(scope, scope_id, period, model_name=model_name)
        if existing is None:
            budget = GatewayBudget(
                scope=scope,
                scope_id=scope_id,
                period=period,
                model_name=model_name,
                limit_usd=limit_usd,
                limit_tokens=limit_tokens,
                limit_requests=limit_requests,
                reset_at=reset_at,
            )
            self._session.add(budget)
            await self._session.flush()
            return budget
        existing.limit_usd = limit_usd
        existing.limit_tokens = limit_tokens
        existing.limit_requests = limit_requests
        if reset_at is not None:
            existing.reset_at = reset_at
        await self._session.flush()
        return existing

    async def settle_usage(
        self,
        budget_id: uuid.UUID,
        *,
        delta_usd: Decimal,
        delta_tokens: int,
        delta_requests: int,
    ) -> None:
        """正向结算：增加用量计数"""
        await self._session.execute(
            update(GatewayBudget)
            .where(GatewayBudget.id == budget_id)
            .values(
                current_usd=GatewayBudget.current_usd + delta_usd,
                current_tokens=GatewayBudget.current_tokens + delta_tokens,
                current_requests=GatewayBudget.current_requests + delta_requests,
            )
        )

    async def reset(self, budget_id: uuid.UUID) -> None:
        await self._session.execute(
            update(GatewayBudget)
            .where(GatewayBudget.id == budget_id)
            .values(current_usd=Decimal("0"), current_tokens=0, current_requests=0)
        )

    async def delete(self, budget_id: uuid.UUID) -> bool:
        budget = await self.get(budget_id)
        if budget is None:
            return False
        await self._session.delete(budget)
        await self._session.flush()
        return True


__all__ = ["BudgetRepository"]
