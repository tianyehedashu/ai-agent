"""GatewayAlertRule / GatewayAlertEvent 仓储（多租户 + system 表）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from domains.gateway.infrastructure.models.alert import GatewayAlertEvent, GatewayAlertRule
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayAlertRule
from libs.db.base_repository import TenantScopedRepositoryBase

if TYPE_CHECKING:
    from decimal import Decimal
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayAlertRepository(TenantScopedRepositoryBase[GatewayAlertRule]):
    """租户告警规则；系统级规则见 ``list_system``。"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self._session = session

    @property
    def model_class(self) -> type[GatewayAlertRule]:
        return GatewayAlertRule

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[GatewayAlertRule]:
        stmt = (
            select(GatewayAlertRule)
            .where(GatewayAlertRule.tenant_id == tenant_id)
            .order_by(GatewayAlertRule.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_rules_for_tenant(self, tenant_id: uuid.UUID) -> list[GatewayAlertRule]:
        return await self.list_for_tenant(tenant_id)

    async def list_system(self, *, only_enabled: bool = False) -> list[SystemGatewayAlertRule]:
        clauses: list[object] = []
        if only_enabled:
            clauses.append(SystemGatewayAlertRule.enabled.is_(True))
        stmt = select(SystemGatewayAlertRule).where(*clauses).order_by(
            SystemGatewayAlertRule.name
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_events_for_tenant(
        self, tenant_id: uuid.UUID, *, limit: int
    ) -> list[GatewayAlertEvent]:
        stmt = (
            select(GatewayAlertEvent)
            .where(GatewayAlertEvent.tenant_id == tenant_id)
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
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
        metric: str,
        threshold: Decimal,
        window_minutes: int,
        channels: dict[str, Any],
        enabled: bool,
    ) -> GatewayAlertRule:
        rule = GatewayAlertRule(
            tenant_id=tenant_id,
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
