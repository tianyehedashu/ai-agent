"""GatewayAlertRule / GatewayAlertEvent 仓储"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from domains.gateway.infrastructure.models.alert import GatewayAlertEvent, GatewayAlertRule

if TYPE_CHECKING:
    from decimal import Decimal
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_rules_by_team(self, team_id: uuid.UUID) -> list[GatewayAlertRule]:
        stmt = select(GatewayAlertRule).where(GatewayAlertRule.team_id == team_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_events_by_team(
        self, team_id: uuid.UUID, *, limit: int
    ) -> list[GatewayAlertEvent]:
        stmt = (
            select(GatewayAlertEvent)
            .where(GatewayAlertEvent.team_id == team_id)
            .order_by(GatewayAlertEvent.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_rule(self, rule_id: uuid.UUID) -> GatewayAlertRule | None:
        return await self._session.get(GatewayAlertRule, rule_id)

    async def create_rule(
        self,
        *,
        team_id: uuid.UUID,
        name: str,
        description: str | None,
        metric: str,
        threshold: Decimal,
        window_minutes: int,
        channels: dict[str, Any],
        enabled: bool,
    ) -> GatewayAlertRule:
        rule = GatewayAlertRule(
            team_id=team_id,
            name=name,
            description=description,
            metric=metric,
            threshold=threshold,
            window_minutes=window_minutes,
            channels=channels,
            enabled=enabled,
        )
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def update_rule_fields(
        self, rule: GatewayAlertRule, fields: dict[str, Any]
    ) -> GatewayAlertRule:
        for field, value in fields.items():
            setattr(rule, field, value)
        await self._session.flush()
        return rule

    async def delete_rule(self, rule: GatewayAlertRule) -> None:
        await self._session.delete(rule)
        await self._session.flush()


__all__ = ["GatewayAlertRepository"]
