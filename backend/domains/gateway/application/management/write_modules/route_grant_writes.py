"""路由跨团队共享授权写服务（写侧分包）。

- ``grant_route_to_team`` / ``update_route_grant_alias``：仅路由创建者本人。
- ``revoke_route_grant``：创建者本人 ∨ 目标团队 owner/admin。
- 变更后 ``reload_litellm_router``（grant 影响 Router deployment 装配）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.errors import ManagementEntityNotFoundError
from domains.gateway.domain.policies.route_grant_access import (
    assert_actor_owns_route,
    assert_alias_free_in_team,
    assert_can_revoke_route_grant,
    normalize_exposed_alias,
)
from domains.tenancy.domain.policies.team_role import is_admin_or_owner_team_role
from libs.exceptions import ValidationError

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.gateway_route_team_grant import (
        GatewayRouteTeamGrant,
    )


class RouteGrantWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def _local_alias_namespace(
        self, tenant_id: uuid.UUID
    ) -> tuple[set[str], set[str]]:
        """团队 T 内本地 model 名 + route 虚拟名（用于别名冲突校验）。"""
        models = await self._models.list_for_tenant(tenant_id, only_enabled=False)
        routes = await self._routes.list_for_tenant(tenant_id, only_enabled=False)
        return ({m.name for m in models}, {r.virtual_model for r in routes})

    async def _assert_actor_member_of_target(
        self,
        *,
        actor_user_id: uuid.UUID,
        target_tenant_id: uuid.UUID,
        route_tenant_id: uuid.UUID,
    ) -> None:
        if target_tenant_id == route_tenant_id:
            raise ValidationError("不能把路由共享给其所属团队（已天然可用）")
        memberships = await self._teams.list_gateway_team_memberships(
            actor_user_id,
            is_platform_admin=False,
        )
        target = next((m for m in memberships if m.team_id == target_tenant_id), None)
        if target is None:
            raise ValidationError("目标团队不是你的成员团队，无法共享")
        if getattr(target, "kind", None) == "personal":
            raise ValidationError("不能把路由共享给个人团队")

    async def grant_route_to_team(
        self,
        *,
        route_id: uuid.UUID,
        target_tenant_id: uuid.UUID,
        exposed_alias: str | None,
        actor_user_id: uuid.UUID,
    ) -> GatewayRouteTeamGrant:
        route = await self._routes.get(route_id)
        if route is None:
            raise ManagementEntityNotFoundError("route", str(route_id))
        assert_actor_owns_route(
            route_id=str(route_id),
            route_created_by_user_id=route.created_by_user_id,
            actor_user_id=actor_user_id,
        )
        await self._assert_actor_member_of_target(
            actor_user_id=actor_user_id,
            target_tenant_id=target_tenant_id,
            route_tenant_id=route.tenant_id,
        )
        alias = normalize_exposed_alias(exposed_alias, default=route.virtual_model)
        local_models, local_routes = await self._local_alias_namespace(target_tenant_id)
        existing_alias = await self._route_grants.get_active_alias(target_tenant_id, alias)
        other_in_use = existing_alias is not None and existing_alias.route_id != route_id
        assert_alias_free_in_team(
            alias,
            local_model_names=local_models,
            local_route_virtual_models=local_routes,
            other_grant_alias_in_use=other_in_use,
        )
        grant = await self._route_grants.upsert_active(
            route_id=route_id,
            tenant_id=target_tenant_id,
            exposed_alias=alias,
            granted_by_user_id=actor_user_id,
        )
        await self.reload_litellm_router()
        return grant

    async def update_route_grant_alias(
        self,
        *,
        route_id: uuid.UUID,
        target_tenant_id: uuid.UUID,
        exposed_alias: str,
        actor_user_id: uuid.UUID,
    ) -> GatewayRouteTeamGrant:
        route = await self._routes.get(route_id)
        if route is None:
            raise ManagementEntityNotFoundError("route", str(route_id))
        assert_actor_owns_route(
            route_id=str(route_id),
            route_created_by_user_id=route.created_by_user_id,
            actor_user_id=actor_user_id,
        )
        alias = normalize_exposed_alias(exposed_alias, default=route.virtual_model)
        local_models, local_routes = await self._local_alias_namespace(target_tenant_id)
        existing_alias = await self._route_grants.get_active_alias(target_tenant_id, alias)
        other_in_use = existing_alias is not None and existing_alias.route_id != route_id
        assert_alias_free_in_team(
            alias,
            local_model_names=local_models,
            local_route_virtual_models=local_routes,
            other_grant_alias_in_use=other_in_use,
        )
        updated = await self._route_grants.update_alias(
            route_id, target_tenant_id, exposed_alias=alias
        )
        if updated is None:
            raise ManagementEntityNotFoundError("route_grant", str(route_id))
        await self.reload_litellm_router()
        return updated

    async def revoke_route_grant(
        self,
        *,
        route_id: uuid.UUID,
        target_tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_team_role: str | None = None,
        reason: str = "owner_revoked",
    ) -> None:
        grant = await self._route_grants.get_active(route_id, target_tenant_id)
        if grant is None:
            raise ManagementEntityNotFoundError("route_grant", str(route_id))
        route = await self._routes.get(route_id)
        route_owner = route.created_by_user_id if route is not None else grant.granted_by_user_id
        assert_can_revoke_route_grant(
            route_created_by_user_id=route_owner,
            actor_user_id=actor_user_id,
            actor_team_role=actor_team_role,
        )
        await self._route_grants.revoke(route_id, target_tenant_id, reason=reason)
        await self.reload_litellm_router()

    async def revoke_route_grant_by_id_for_team(
        self,
        *,
        grant_id: uuid.UUID,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        actor_team_role: str | None,
        reason: str = "team_admin_revoked",
    ) -> None:
        """团队侧按 grant_id 踢出：仅目标团队 owner/admin。"""
        grant = await self._route_grants.get(grant_id)
        if grant is None or grant.tenant_id != team_id or not grant.is_active:
            raise ManagementEntityNotFoundError("route_grant", str(grant_id))
        if not is_admin_or_owner_team_role(actor_team_role):
            route = await self._routes.get(grant.route_id)
            route_owner = (
                route.created_by_user_id if route is not None else grant.granted_by_user_id
            )
            assert_can_revoke_route_grant(
                route_created_by_user_id=route_owner,
                actor_user_id=actor_user_id,
                actor_team_role=actor_team_role,
            )
        await self._route_grants.revoke(grant.route_id, team_id, reason=reason)
        await self.reload_litellm_router()

    async def _cascade_revoke_route_grants(
        self, route_id: uuid.UUID, *, reason: str = "route_deleted"
    ) -> int:
        """路由删除时级联软撤销其全部 grant（由 delete_gateway_route 调用，复用其 reload）。"""
        return await self._route_grants.revoke_all_for_route(route_id, reason=reason)


__all__ = ["RouteGrantWritesMixin"]
