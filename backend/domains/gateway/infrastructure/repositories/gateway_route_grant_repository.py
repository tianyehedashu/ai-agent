"""GatewayRouteTeamGrantRepository — 路由跨团队共享授权行 CRUD。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from domains.gateway.infrastructure.models.gateway_route_team_grant import (
    GatewayRouteTeamGrant,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayRouteTeamGrantRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    # ─── 读 ────────────────────────────────────────────────────────────────

    async def get_active(
        self, route_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> GatewayRouteTeamGrant | None:
        stmt = select(GatewayRouteTeamGrant).where(
            GatewayRouteTeamGrant.route_id == route_id,
            GatewayRouteTeamGrant.tenant_id == tenant_id,
            GatewayRouteTeamGrant.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_by_tenant_alias(
        self, tenant_id: uuid.UUID, exposed_alias: str
    ) -> GatewayRouteTeamGrant | None:
        """代理热路径：按 (T, 暴露别名) 查 active grant。"""
        stmt = select(GatewayRouteTeamGrant).where(
            GatewayRouteTeamGrant.tenant_id == tenant_id,
            GatewayRouteTeamGrant.exposed_alias == exposed_alias,
            GatewayRouteTeamGrant.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_alias(
        self, tenant_id: uuid.UUID, exposed_alias: str
    ) -> GatewayRouteTeamGrant | None:
        """别名占用检查（创建/改名/本地命名冲突校验共用）。"""
        return await self.resolve_by_tenant_alias(tenant_id, exposed_alias)

    async def list_active_for_route(
        self, route_id: uuid.UUID
    ) -> list[GatewayRouteTeamGrant]:
        stmt = (
            select(GatewayRouteTeamGrant)
            .where(
                GatewayRouteTeamGrant.route_id == route_id,
                GatewayRouteTeamGrant.is_active.is_(True),
            )
            .order_by(GatewayRouteTeamGrant.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_for_tenant(
        self, tenant_id: uuid.UUID
    ) -> list[GatewayRouteTeamGrant]:
        """团队侧"共享进来的路由"列表 + 列表读路径。"""
        stmt = (
            select(GatewayRouteTeamGrant)
            .where(
                GatewayRouteTeamGrant.tenant_id == tenant_id,
                GatewayRouteTeamGrant.is_active.is_(True),
            )
            .order_by(GatewayRouteTeamGrant.exposed_alias.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all_active(self) -> list[GatewayRouteTeamGrant]:
        """Router 装配：全部 active grant。"""
        stmt = select(GatewayRouteTeamGrant).where(
            GatewayRouteTeamGrant.is_active.is_(True)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_active_consumer_tenant_ids(self) -> set[uuid.UUID]:
        """所有活跃 grant 的消费团队去重集合。

        owner 侧底层资源（模型/凭据）变更时，委派 resolve 缓存按**消费团队**键存放，
        不会被 owner 租户失效命中；据此连带失效持有共享路由的消费团队。
        """
        stmt = (
            select(GatewayRouteTeamGrant.tenant_id)
            .where(GatewayRouteTeamGrant.is_active.is_(True))
            .distinct()
        )
        result = await self._session.execute(stmt)
        return set(result.scalars().all())

    async def get(self, grant_id: uuid.UUID) -> GatewayRouteTeamGrant | None:
        return await self._session.get(GatewayRouteTeamGrant, grant_id)

    # ─── 写 ────────────────────────────────────────────────────────────────

    async def upsert_active(
        self,
        *,
        route_id: uuid.UUID,
        tenant_id: uuid.UUID,
        exposed_alias: str,
        granted_by_user_id: uuid.UUID,
    ) -> GatewayRouteTeamGrant:
        """幂等插入 active grant（先查后插）；命中已存在行时按需更新暴露别名。"""
        existing = await self.get_active(route_id, tenant_id)
        if existing is not None:
            if existing.exposed_alias != exposed_alias:
                existing.exposed_alias = exposed_alias
                await self._session.flush()
            return existing

        grant = GatewayRouteTeamGrant(
            route_id=route_id,
            tenant_id=tenant_id,
            exposed_alias=exposed_alias,
            granted_by_user_id=granted_by_user_id,
            is_active=True,
        )
        self._session.add(grant)
        await self._session.flush()
        return grant

    async def update_alias(
        self, route_id: uuid.UUID, tenant_id: uuid.UUID, *, exposed_alias: str
    ) -> GatewayRouteTeamGrant | None:
        grant = await self.get_active(route_id, tenant_id)
        if grant is None:
            return None
        grant.exposed_alias = exposed_alias
        await self._session.flush()
        return grant

    async def revoke(
        self, route_id: uuid.UUID, tenant_id: uuid.UUID, *, reason: str
    ) -> bool:
        grant = await self.get_active(route_id, tenant_id)
        if grant is None:
            return False
        grant.revoke(reason)
        await self._session.flush()
        return True

    async def revoke_all_for_route(
        self, route_id: uuid.UUID, *, reason: str = "route_deleted"
    ) -> int:
        """路由删除时撤销其全部 grant。"""
        return await self._bulk_revoke(
            GatewayRouteTeamGrant.route_id == route_id, reason=reason
        )

    async def revoke_grants_for_user_team(
        self,
        *,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        reason: str = "membership_lost",
    ) -> int:
        """成员移除：撤销该用户共享进指定 team 的全部 grant。"""
        return await self._bulk_revoke(
            GatewayRouteTeamGrant.granted_by_user_id == user_id,
            GatewayRouteTeamGrant.tenant_id == tenant_id,
            reason=reason,
        )

    async def revoke_all_for_tenant(
        self, tenant_id: uuid.UUID, *, reason: str = "team_archived"
    ) -> int:
        """团队删除：撤销指向该 team 的全部 grant。"""
        return await self._bulk_revoke(
            GatewayRouteTeamGrant.tenant_id == tenant_id, reason=reason
        )

    async def _bulk_revoke(self, *clauses: object, reason: str) -> int:
        stmt = (
            update(GatewayRouteTeamGrant)
            .where(GatewayRouteTeamGrant.is_active.is_(True), *clauses)
            .values(is_active=False, revoked_at=datetime.now(UTC), revoked_reason=reason)
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]

    async def list_active_by_tenants(
        self, tenant_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, list[GatewayRouteTeamGrant]]:
        """批量预取：tenant_id → active grant 行。"""
        if not tenant_ids:
            return {}
        stmt = select(GatewayRouteTeamGrant).where(
            GatewayRouteTeamGrant.tenant_id.in_(tenant_ids),
            GatewayRouteTeamGrant.is_active.is_(True),
        )
        result = await self._session.execute(stmt)
        grouped: dict[uuid.UUID, list[GatewayRouteTeamGrant]] = {}
        for grant in result.scalars().all():
            grouped.setdefault(grant.tenant_id, []).append(grant)
        return grouped


__all__ = ["GatewayRouteTeamGrantRepository"]
