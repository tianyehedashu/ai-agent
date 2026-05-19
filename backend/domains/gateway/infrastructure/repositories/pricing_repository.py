"""Upstream / Downstream pricing 仓储。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal  # noqa: TC003
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, or_, select

from domains.gateway.infrastructure.models.pricing_downstream import DownstreamModelPricing
from domains.gateway.infrastructure.models.pricing_upstream import UpstreamModelPricing

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


def _active_at_clause(effective_from_col, effective_to_col, at: datetime):
    return and_(
        effective_from_col <= at,
        or_(effective_to_col.is_(None), effective_to_col > at),
    )


class UpstreamPricingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active(
        self,
        *,
        provider: str,
        upstream_model: str,
        capability: str,
        at: datetime | None = None,
    ) -> UpstreamModelPricing | None:
        at = at or datetime.now(UTC)
        stmt = (
            select(UpstreamModelPricing)
            .where(
                UpstreamModelPricing.provider == provider,
                UpstreamModelPricing.upstream_model == upstream_model,
                UpstreamModelPricing.capability == capability,
                _active_at_clause(
                    UpstreamModelPricing.effective_from,
                    UpstreamModelPricing.effective_to,
                    at,
                ),
            )
            .order_by(UpstreamModelPricing.effective_from.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_active(
        self,
        *,
        provider: str | None = None,
        at: datetime | None = None,
    ) -> list[UpstreamModelPricing]:
        at = at or datetime.now(UTC)
        clauses = [
            _active_at_clause(
                UpstreamModelPricing.effective_from,
                UpstreamModelPricing.effective_to,
                at,
            )
        ]
        if provider:
            clauses.append(UpstreamModelPricing.provider == provider)
        stmt = select(UpstreamModelPricing).where(and_(*clauses))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        provider: str,
        upstream_model: str,
        capability: str,
        input_cost_per_token: Decimal,
        output_cost_per_token: Decimal,
        cache_creation_input_token_cost: Decimal | None = None,
        cache_read_input_token_cost: Decimal | None = None,
        extra: dict[str, Any] | None = None,
        effective_from: datetime | None = None,
        source: str = "manual",
        version: int = 1,
    ) -> UpstreamModelPricing:
        row = UpstreamModelPricing(
            provider=provider,
            upstream_model=upstream_model,
            capability=capability,
            input_cost_per_token=input_cost_per_token,
            output_cost_per_token=output_cost_per_token,
            cache_creation_input_token_cost=cache_creation_input_token_cost,
            cache_read_input_token_cost=cache_read_input_token_cost,
            extra=extra,
            effective_from=effective_from or datetime.now(UTC),
            source=source,
            version=version,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_id(self, row_id: uuid.UUID) -> UpstreamModelPricing | None:
        return await self._session.get(UpstreamModelPricing, row_id)

    async def close_effective(
        self, row: UpstreamModelPricing, *, at: datetime | None = None
    ) -> None:
        row.effective_to = at or datetime.now(UTC)
        await self._session.flush()


class DownstreamPricingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_for_scope(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        gateway_model_id: uuid.UUID | None,
        at: datetime | None = None,
    ) -> DownstreamModelPricing | None:
        at = at or datetime.now(UTC)
        clauses = [
            DownstreamModelPricing.scope == scope,
            _active_at_clause(
                DownstreamModelPricing.effective_from,
                DownstreamModelPricing.effective_to,
                at,
            ),
        ]
        if scope_id is None:
            clauses.append(DownstreamModelPricing.scope_id.is_(None))
        else:
            clauses.append(DownstreamModelPricing.scope_id == scope_id)
        if gateway_model_id is None:
            clauses.append(DownstreamModelPricing.gateway_model_id.is_(None))
        else:
            clauses.append(DownstreamModelPricing.gateway_model_id == gateway_model_id)
        stmt = (
            select(DownstreamModelPricing)
            .where(and_(*clauses))
            .order_by(DownstreamModelPricing.effective_from.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_scope(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        at: datetime | None = None,
    ) -> list[DownstreamModelPricing]:
        at = at or datetime.now(UTC)
        clauses = [
            DownstreamModelPricing.scope == scope,
            _active_at_clause(
                DownstreamModelPricing.effective_from,
                DownstreamModelPricing.effective_to,
                at,
            ),
        ]
        if scope_id is None:
            clauses.append(DownstreamModelPricing.scope_id.is_(None))
        else:
            clauses.append(DownstreamModelPricing.scope_id == scope_id)
        stmt = select(DownstreamModelPricing).where(and_(*clauses))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        gateway_model_id: uuid.UUID | None,
        inheritance_strategy: str,
        input_cost_per_token: Decimal | None = None,
        output_cost_per_token: Decimal | None = None,
        cache_creation_input_token_cost: Decimal | None = None,
        cache_read_input_token_cost: Decimal | None = None,
        per_request_usd: Decimal | None = None,
        extra: dict[str, Any] | None = None,
        effective_from: datetime | None = None,
        version: int = 1,
    ) -> DownstreamModelPricing:
        row = DownstreamModelPricing(
            scope=scope,
            scope_id=scope_id,
            gateway_model_id=gateway_model_id,
            inheritance_strategy=inheritance_strategy,
            input_cost_per_token=input_cost_per_token,
            output_cost_per_token=output_cost_per_token,
            cache_creation_input_token_cost=cache_creation_input_token_cost,
            cache_read_input_token_cost=cache_read_input_token_cost,
            per_request_usd=per_request_usd,
            extra=extra,
            effective_from=effective_from or datetime.now(UTC),
            version=version,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_by_id(self, row_id: uuid.UUID) -> DownstreamModelPricing | None:
        return await self._session.get(DownstreamModelPricing, row_id)

    async def close_effective(
        self, row: DownstreamModelPricing, *, at: datetime | None = None
    ) -> None:
        row.effective_to = at or datetime.now(UTC)
        await self._session.flush()


__all__ = ["DownstreamPricingRepository", "UpstreamPricingRepository"]
