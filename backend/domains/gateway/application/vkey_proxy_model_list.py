"""跨 team vkey 代理端 GET /v1/models 列表编排。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.entitlement_model_status import resolve_entitlement_scope
from domains.gateway.application.gateway_model_listing import GatewayRegistryModelRow
from domains.gateway.application.management import GatewayManagementReadService
from domains.gateway.application.proxy_model_list_reads import build_proxy_models_list
from domains.gateway.application.vkey_team_resolution import get_slug_by_tenant_id_map
from domains.gateway.domain.policies.model_selection import registry_kind_for_merged_row
from domains.gateway.domain.vkey_team_prefix_policy import resolve_vkey_proxy_list_id
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.domain.types import VirtualKeyPrincipal
    from domains.gateway.presentation.deps import VkeyOrApikeyPrincipal

logger = get_logger(__name__)

RouteRow = GatewayRoute | SystemGatewayRoute


def _resolve_allowed_set(principal: VkeyOrApikeyPrincipal) -> set[str] | None:
    allowed: set[str] | None = None
    if principal.vkey and principal.vkey.allowed_models:
        allowed = set(principal.vkey.allowed_models)
    if principal.api_key_grant and principal.api_key_grant.allowed_models:
        grant_allowed = set(principal.api_key_grant.allowed_models)
        allowed = grant_allowed if allowed is None else allowed & grant_allowed
    return allowed


def _filter_models(
    models: list[GatewayRegistryModelRow],
    allowed: set[str] | None,
) -> list[GatewayRegistryModelRow]:
    if allowed is None:
        return models
    return [m for m in models if m.name in allowed]


def _filter_routes(routes: list[RouteRow], allowed: set[str] | None) -> list[RouteRow]:
    if allowed is None:
        return routes
    return [r for r in routes if r.virtual_model in allowed]


def _ordered_grant_tenant_ids(vkey: VirtualKeyPrincipal) -> tuple[uuid.UUID, ...]:
    """主属 team 优先，便于 system 裸名先进入 dedupe 集合。"""
    others = tuple(tid for tid in vkey.granted_team_ids if tid != vkey.team_id)
    return (vkey.team_id, *others)


def _should_skip_grant_system_row(
    *,
    tenant_id: uuid.UUID,
    bound_team_id: uuid.UUID,
    row: GatewayRegistryModelRow,
    bound_system_registry_names: set[str],
) -> bool:
    """grant team 的 system 行若主属已以裸名列出，则跳过 prefixed 重复。"""
    if tenant_id == bound_team_id:
        return False
    if registry_kind_for_merged_row(row) != "system":
        return False
    return row.name in bound_system_registry_names


async def _list_callable_for_team(
    reads: GatewayManagementReadService,
    tenant_id: uuid.UUID,
    *,
    user_id: uuid.UUID | None,
) -> tuple[list[GatewayRegistryModelRow], list[RouteRow]]:
    models = await reads.list_gateway_models(
        tenant_id,
        registry_scope="callable",
        only_enabled=True,
        user_id=user_id,
    )
    routes = await reads.list_gateway_routes(tenant_id, only_enabled=True)
    return models, routes


async def list_proxy_models_for_team(
    session: AsyncSession,
    *,
    team_id: uuid.UUID,
    user_id: uuid.UUID | None,
    allowed: set[str] | None,
    entitlement_scope: str | None,
    entitlement_scope_id: uuid.UUID | None,
) -> list[dict[str, object]]:
    """单 team callable 模型列表（apikey / 单 grant vkey fast path）。"""
    reads = GatewayManagementReadService(session)
    all_models, routes = await _list_callable_for_team(reads, team_id, user_id=user_id)
    visible_models = _filter_models(all_models, allowed)
    visible_routes = _filter_routes(routes, allowed)
    return await build_proxy_models_list(
        session,
        visible_models,
        routes=visible_routes,
        entitlement_scope=entitlement_scope,
        entitlement_scope_id=entitlement_scope_id,
        route_lookup_models=all_models,
    )


async def list_proxy_models_for_multi_grant_vkey(
    session: AsyncSession,
    *,
    vkey: VirtualKeyPrincipal,
    user_id: uuid.UUID | None,
    allowed: set[str] | None,
    entitlement_scope: str | None,
    entitlement_scope_id: uuid.UUID | None,
) -> list[dict[str, object]]:
    """multi-grant vkey：合并各 grant team callable 列表，id 与 dispatch 对称。"""
    reads = GatewayManagementReadService(session)
    slug_by_tenant = await get_slug_by_tenant_id_map(session, vkey.granted_team_ids)

    visible_models: list[GatewayRegistryModelRow] = []
    model_list_ids: list[str] = []
    model_team_slugs: list[str | None] = []

    visible_routes: list[RouteRow] = []
    route_list_ids: list[str] = []
    route_team_slugs: list[str | None] = []
    route_lookup_pools: list[list[GatewayRegistryModelRow]] = []

    all_models_pool: list[GatewayRegistryModelRow] = []
    seen_list_ids: set[str] = set()
    bound_system_registry_names: set[str] = set()

    for tenant_id in _ordered_grant_tenant_ids(vkey):
        if tenant_id not in slug_by_tenant:
            logger.warning(
                "skip stale vkey grant tenant_id=%s vkey_id=%s (team row missing)",
                tenant_id,
                vkey.vkey_id,
            )
            continue

        team_slug = slug_by_tenant[tenant_id]
        all_models, routes = await _list_callable_for_team(
            reads, tenant_id, user_id=user_id
        )
        all_models_pool.extend(all_models)

        for row in _filter_models(all_models, allowed):
            if _should_skip_grant_system_row(
                tenant_id=tenant_id,
                bound_team_id=vkey.team_id,
                row=row,
                bound_system_registry_names=bound_system_registry_names,
            ):
                continue

            list_id = resolve_vkey_proxy_list_id(
                bound_team_id=vkey.team_id,
                model_tenant_id=tenant_id,
                model_name=row.name,
                slug_by_tenant=slug_by_tenant,
            )
            if list_id in seen_list_ids:
                continue
            seen_list_ids.add(list_id)

            if tenant_id == vkey.team_id and registry_kind_for_merged_row(row) == "system":
                bound_system_registry_names.add(row.name)

            visible_models.append(row)
            model_list_ids.append(list_id)
            model_team_slugs.append(
                None if tenant_id == vkey.team_id else team_slug
            )

        tenant_routes = _filter_routes(routes, allowed)
        for route in tenant_routes:
            if (
                tenant_id != vkey.team_id
                and route.virtual_model in bound_system_registry_names
                and isinstance(route, SystemGatewayRoute)
            ):
                continue

            list_id = resolve_vkey_proxy_list_id(
                bound_team_id=vkey.team_id,
                model_tenant_id=tenant_id,
                model_name=route.virtual_model,
                slug_by_tenant=slug_by_tenant,
            )
            if list_id in seen_list_ids:
                continue
            seen_list_ids.add(list_id)

            visible_routes.append(route)
            route_list_ids.append(list_id)
            route_team_slugs.append(
                None if tenant_id == vkey.team_id else team_slug
            )
            route_lookup_pools.append(all_models)

    return await build_proxy_models_list(
        session,
        visible_models,
        routes=visible_routes,
        entitlement_scope=entitlement_scope,
        entitlement_scope_id=entitlement_scope_id,
        route_lookup_models=all_models_pool,
        model_list_ids=model_list_ids,
        model_team_slugs=model_team_slugs,
        route_list_ids=route_list_ids,
        route_team_slugs=route_team_slugs,
        route_lookup_pools=route_lookup_pools,
        include_extended_gateway_metadata=True,
    )


async def list_openai_proxy_models(
    session: AsyncSession,
    principal: VkeyOrApikeyPrincipal,
) -> list[dict[str, object]]:
    """GET /v1/models 统一入口。"""
    entitlement_scope, entitlement_scope_id = resolve_entitlement_scope(
        vkey_id=principal.vkey.vkey_id if principal.vkey else None,
        apikey_grant_id=principal.api_key_grant.grant_id if principal.api_key_grant else None,
    )
    allowed = _resolve_allowed_set(principal)

    if (
        principal.vkey is not None
        and not principal.vkey.is_system
        and len(principal.vkey.granted_team_ids) > 1
    ):
        return await list_proxy_models_for_multi_grant_vkey(
            session,
            vkey=principal.vkey,
            user_id=principal.user_id,
            allowed=allowed,
            entitlement_scope=entitlement_scope,
            entitlement_scope_id=entitlement_scope_id,
        )

    return await list_proxy_models_for_team(
        session,
        team_id=principal.team_id,
        user_id=principal.user_id,
        allowed=allowed,
        entitlement_scope=entitlement_scope,
        entitlement_scope_id=entitlement_scope_id,
    )


__all__ = [
    "_ordered_grant_tenant_ids",
    "_should_skip_grant_system_row",
    "list_openai_proxy_models",
    "list_proxy_models_for_multi_grant_vkey",
    "list_proxy_models_for_team",
]
