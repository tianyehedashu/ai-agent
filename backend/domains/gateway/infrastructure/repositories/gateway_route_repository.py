"""GatewayRouteRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from domains.gateway.domain.policies.model_selection import (
    merge_virtual_model_rows_tenant_overrides_system,
)
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class GatewayRouteRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, route_id: uuid.UUID) -> GatewayRoute | None:
        return await self._session.get(GatewayRoute, route_id)

    async def list_system(
        self,
        *,
        only_enabled: bool = True,
    ) -> list[SystemGatewayRoute]:
        clauses: list[object] = []
        if only_enabled:
            clauses.append(SystemGatewayRoute.enabled.is_(True))
        stmt = select(SystemGatewayRoute).where(*clauses).order_by(SystemGatewayRoute.virtual_model)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        only_enabled: bool = True,
    ) -> list[GatewayRoute | SystemGatewayRoute]:
        """租户路由 + system 路由合并（tenant 同名 ``virtual_model`` 优先）。"""
        return await self.list_merged_routes_for_tenants(
            [tenant_id],
            only_enabled=only_enabled,
        )

    async def list_merged_routes_for_tenants(
        self,
        tenant_ids: list[uuid.UUID],
        *,
        only_enabled: bool = True,
    ) -> list[GatewayRoute | SystemGatewayRoute]:
        """多租户路由聚合：各 tenant 与 system 合并后按 route id 去重。"""
        if not tenant_ids:
            return []

        clauses: list[object] = [GatewayRoute.tenant_id.in_(tenant_ids)]
        if only_enabled:
            clauses.append(GatewayRoute.enabled.is_(True))
        stmt = select(GatewayRoute).where(*clauses).order_by(GatewayRoute.virtual_model)
        result = await self._session.execute(stmt)
        all_tenant_rows = list(result.scalars().all())

        by_tenant: dict[uuid.UUID, list[GatewayRoute]] = {}
        for row in all_tenant_rows:
            if row.tenant_id is not None:
                by_tenant.setdefault(row.tenant_id, []).append(row)

        system_rows = await self.list_system(only_enabled=only_enabled)
        by_id: dict[uuid.UUID, GatewayRoute | SystemGatewayRoute] = {}
        for tenant_id in tenant_ids:
            tenant_rows = by_tenant.get(tenant_id, [])
            merged = merge_virtual_model_rows_tenant_overrides_system(
                tenant_rows,
                system_rows,
                only_enabled=only_enabled,
            )
            for route in merged:
                by_id[route.id] = route

        return sorted(by_id.values(), key=lambda row: row.virtual_model)

    async def list_all_active(self) -> list[GatewayRoute]:
        stmt = select(GatewayRoute).where(GatewayRoute.enabled.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_system_by_virtual_model(self, virtual_model: str) -> SystemGatewayRoute | None:
        stmt = (
            select(SystemGatewayRoute)
            .where(
                SystemGatewayRoute.virtual_model == virtual_model,
                SystemGatewayRoute.enabled.is_(True),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_virtual_model(
        self, team_id: uuid.UUID | None, virtual_model: str
    ) -> GatewayRoute | None:
        if team_id is None:
            return None
        stmt = (
            select(GatewayRoute)
            .where(
                GatewayRoute.virtual_model == virtual_model,
                GatewayRoute.enabled.is_(True),
                GatewayRoute.tenant_id == team_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_virtual_model_for_tenant(
        self, tenant_id: uuid.UUID, virtual_model: str
    ) -> GatewayRoute | None:
        """检查指定租户是否存在同名虚拟路由（含已禁用），用于创建前重复检查。"""
        stmt = (
            select(GatewayRoute)
            .where(
                GatewayRoute.virtual_model == virtual_model,
                GatewayRoute.tenant_id == tenant_id,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_by_virtual_model(
        self, team_id: uuid.UUID | None, virtual_model: str
    ) -> GatewayRoute | SystemGatewayRoute | None:
        if team_id is not None:
            tenant_row = await self.get_by_virtual_model(team_id, virtual_model)
            if tenant_row is not None:
                return tenant_row
        return await self.get_system_by_virtual_model(virtual_model)

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        virtual_model: str,
        primary_models: list[str],
        fallbacks_general: list[str] | None = None,
        fallbacks_content_policy: list[str] | None = None,
        fallbacks_context_window: list[str] | None = None,
        strategy: str = "simple-shuffle",
        retry_policy: dict[str, Any] | None = None,
    ) -> GatewayRoute:
        route = GatewayRoute(
            tenant_id=tenant_id,
            virtual_model=virtual_model,
            primary_models=primary_models,
            fallbacks_general=fallbacks_general or [],
            fallbacks_content_policy=fallbacks_content_policy or [],
            fallbacks_context_window=fallbacks_context_window or [],
            strategy=strategy,
            retry_policy=retry_policy,
        )
        self._session.add(route)
        await self._session.flush()
        return route

    async def update(self, route_id: uuid.UUID, **fields: Any) -> GatewayRoute | None:
        route = await self.get(route_id)
        if route is None:
            return None
        for key, value in fields.items():
            if hasattr(route, key) and value is not None:
                setattr(route, key, value)
        await self._session.flush()
        return route

    async def delete(self, route_id: uuid.UUID) -> bool:
        route = await self.get(route_id)
        if route is None:
            return False
        await self._session.delete(route)
        await self._session.flush()
        return True

    async def remove_model_names_from_all_routes(self, model_names: frozenset[str]) -> int:
        """从所有路由的 primary/fallback 列表中移除已删除的虚拟模型名。"""
        if not model_names:
            return 0
        stmt = select(GatewayRoute)
        routes = list((await self._session.execute(stmt)).scalars().all())
        updated = 0
        array_fields = (
            "primary_models",
            "fallbacks_general",
            "fallbacks_content_policy",
            "fallbacks_context_window",
        )
        for route in routes:
            changed = False
            for field in array_fields:
                current = list(getattr(route, field) or ())
                filtered = [name for name in current if name not in model_names]
                if len(filtered) != len(current):
                    setattr(route, field, filtered)
                    changed = True
            if changed:
                updated += 1
        if updated:
            await self._session.flush()
        return updated

    async def rename_model_name_in_tenant_routes(
        self,
        tenant_id: uuid.UUID,
        old_name: str,
        new_name: str,
    ) -> int:
        """将指定租户路由 primary/fallback 列表中的模型名 old_name 替换为 new_name。"""
        if old_name == new_name:
            return 0
        stmt = select(GatewayRoute).where(GatewayRoute.tenant_id == tenant_id)
        routes = list((await self._session.execute(stmt)).scalars().all())
        updated = self._rename_model_name_in_route_arrays(routes, old_name, new_name)
        if updated:
            await self._session.flush()
        return updated

    async def rename_model_name_in_global_routes(self, old_name: str, new_name: str) -> int:
        """将 ``system_gateway_routes`` 中的模型名 old_name 替换为 new_name。"""
        if old_name == new_name:
            return 0
        stmt = select(SystemGatewayRoute)
        routes = list((await self._session.execute(stmt)).scalars().all())
        updated = 0
        array_fields = (
            "primary_models",
            "fallbacks_general",
            "fallbacks_content_policy",
            "fallbacks_context_window",
        )
        for route in routes:
            changed = False
            for field in array_fields:
                current = list(getattr(route, field) or ())
                if old_name not in current:
                    continue
                setattr(
                    route,
                    field,
                    [new_name if name == old_name else name for name in current],
                )
                changed = True
            if changed:
                updated += 1
        if updated:
            await self._session.flush()
        return updated

    def _rename_model_name_in_route_arrays(
        self,
        routes: list[GatewayRoute],
        old_name: str,
        new_name: str,
    ) -> int:
        array_fields = (
            "primary_models",
            "fallbacks_general",
            "fallbacks_content_policy",
            "fallbacks_context_window",
        )
        updated = 0
        for route in routes:
            changed = False
            for field in array_fields:
                current = list(getattr(route, field) or ())
                if old_name not in current:
                    continue
                setattr(
                    route,
                    field,
                    [new_name if name == old_name else name for name in current],
                )
                changed = True
            if changed:
                updated += 1
        return updated


__all__ = ["GatewayRouteRepository"]
