"""跨 team vkey 代理端 GET /v1/models 列表编排。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.catalog.gateway_model_listing import GatewayRegistryModelRow
from domains.gateway.application.catalog.granted_route_listing import (
    GrantedRouteRow,
    list_granted_route_rows_for_team,
)
from domains.gateway.application.management import GatewayManagementReadService
from domains.gateway.application.proxy.proxy_model_list_reads import build_proxy_models_list
from domains.gateway.application.quota.entitlement_model_status import resolve_entitlement_scope
from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row
from domains.gateway.domain.vkey.vkey_grant_slug_policy import (
    build_slug_by_tenant_id,
    find_ambiguous_grant_slugs,
    grant_tenant_prefix_dispatchable,
)
from domains.gateway.domain.vkey.vkey_proxy_list_policy import (
    ordered_grant_tenant_ids,
    should_include_multi_grant_entry,
    should_skip_grant_system_model_row,
    should_skip_grant_system_route_row,
)
from domains.gateway.domain.vkey.vkey_team_prefix_policy import resolve_vkey_proxy_list_id
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute
from utils.logging import get_logger

from .vkey_team_resolution import fetch_grant_team_slug_rows

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.domain.types import VirtualKeyPrincipal

logger = get_logger(__name__)

RouteRow = GatewayRoute | SystemGatewayRoute | GrantedRouteRow


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


def _is_system_route(route: RouteRow) -> bool:
    return getattr(route, "tenant_id", None) is None


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
    visible_routes: list[RouteRow] = list(_filter_routes(routes, allowed))

    # 跨团队共享授权（委派）：把共享进本团队的路由按暴露别名投影为合成路由行，
    # 并为其提供 owner 团队的可调用模型池以解析 capability。本地路由用本团队模型池。
    granted_rows, granted_pools = await list_granted_route_rows_for_team(
        session, team_id, allowed=allowed
    )
    if granted_rows:
        route_lookup_pools = [all_models for _ in visible_routes] + granted_pools
        visible_routes.extend(granted_rows)
        return await build_proxy_models_list(
            session,
            visible_models,
            routes=visible_routes,
            entitlement_scope=entitlement_scope,
            entitlement_scope_id=entitlement_scope_id,
            route_lookup_models=all_models,
            route_lookup_pools=route_lookup_pools,
        )

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
    slug_rows = await fetch_grant_team_slug_rows(session, vkey.granted_team_ids)
    slug_by_tenant = build_slug_by_tenant_id(slug_rows)
    ambiguous_slugs = find_ambiguous_grant_slugs(slug_rows)

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

    for tenant_id in ordered_grant_tenant_ids(vkey.team_id, vkey.granted_team_ids):
        if tenant_id not in slug_by_tenant:
            logger.warning(
                "skip stale vkey grant tenant_id=%s vkey_id=%s (team row missing)",
                tenant_id,
                vkey.vkey_id,
            )
            continue

        team_slug = slug_by_tenant[tenant_id]
        prefix_dispatchable = grant_tenant_prefix_dispatchable(
            tenant_id=tenant_id,
            bound_team_id=vkey.team_id,
            slug=team_slug,
            ambiguous_slugs=ambiguous_slugs,
        )
        all_models, routes = await _list_callable_for_team(
            reads, tenant_id, user_id=user_id
        )
        all_models_pool.extend(all_models)

        for row in _filter_models(all_models, allowed):
            if should_skip_grant_system_model_row(
                tenant_id=tenant_id,
                bound_team_id=vkey.team_id,
                registry_name=row.name,
                is_system_registry=registry_kind_for_merged_row(row) == "system",
                bound_system_registry_names=frozenset(bound_system_registry_names),
            ):
                continue

            list_id = resolve_vkey_proxy_list_id(
                bound_team_id=vkey.team_id,
                model_tenant_id=tenant_id,
                model_name=row.name,
                slug_by_tenant=slug_by_tenant,
            )
            if not should_include_multi_grant_entry(
                tenant_id=tenant_id,
                bound_team_id=vkey.team_id,
                list_id=list_id,
                seen_list_ids=frozenset(seen_list_ids),
                prefix_dispatchable=prefix_dispatchable,
            ):
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
            if should_skip_grant_system_route_row(
                tenant_id=tenant_id,
                bound_team_id=vkey.team_id,
                virtual_model=route.virtual_model,
                is_system_registry_route=_is_system_route(route),
                bound_system_registry_names=frozenset(bound_system_registry_names),
            ):
                continue

            list_id = resolve_vkey_proxy_list_id(
                bound_team_id=vkey.team_id,
                model_tenant_id=tenant_id,
                model_name=route.virtual_model,
                slug_by_tenant=slug_by_tenant,
            )
            if not should_include_multi_grant_entry(
                tenant_id=tenant_id,
                bound_team_id=vkey.team_id,
                list_id=list_id,
                seen_list_ids=frozenset(seen_list_ids),
                prefix_dispatchable=prefix_dispatchable,
            ):
                continue
            seen_list_ids.add(list_id)

            visible_routes.append(route)
            route_list_ids.append(list_id)
            route_team_slugs.append(
                None if tenant_id == vkey.team_id else team_slug
            )
            route_lookup_pools.append(all_models)

        # 共享进该 team 的路由（委派）：按暴露别名投影，owner 模型池单独提供
        granted_rows, granted_pools = await list_granted_route_rows_for_team(
            session, tenant_id, allowed=allowed
        )
        for granted_row, owner_pool in zip(granted_rows, granted_pools, strict=True):
            list_id = resolve_vkey_proxy_list_id(
                bound_team_id=vkey.team_id,
                model_tenant_id=tenant_id,
                model_name=granted_row.virtual_model,
                slug_by_tenant=slug_by_tenant,
            )
            if not should_include_multi_grant_entry(
                tenant_id=tenant_id,
                bound_team_id=vkey.team_id,
                list_id=list_id,
                seen_list_ids=frozenset(seen_list_ids),
                prefix_dispatchable=prefix_dispatchable,
            ):
                continue
            seen_list_ids.add(list_id)
            visible_routes.append(granted_row)
            route_list_ids.append(list_id)
            route_team_slugs.append(None if tenant_id == vkey.team_id else team_slug)
            route_lookup_pools.append(owner_pool)

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
    *,
    team_id: uuid.UUID,
    user_id: uuid.UUID | None,
    vkey: VirtualKeyPrincipal | None,
    api_key_grant_id: uuid.UUID | None,
    allowed: set[str] | None,
) -> list[dict[str, object]]:
    """GET /v1/models 统一入口（application 层，不依赖 presentation）。"""
    entitlement_scope, entitlement_scope_id = resolve_entitlement_scope(
        vkey_id=vkey.vkey_id if vkey else None,
        apikey_grant_id=api_key_grant_id,
    )

    if (
        vkey is not None
        and not vkey.is_system
        and len(vkey.granted_team_ids) > 1
    ):
        return await list_proxy_models_for_multi_grant_vkey(
            session,
            vkey=vkey,
            user_id=user_id,
            allowed=allowed,
            entitlement_scope=entitlement_scope,
            entitlement_scope_id=entitlement_scope_id,
        )

    return await list_proxy_models_for_team(
        session,
        team_id=team_id,
        user_id=user_id,
        allowed=allowed,
        entitlement_scope=entitlement_scope,
        entitlement_scope_id=entitlement_scope_id,
    )


__all__ = [
    "list_openai_proxy_models",
    "list_proxy_models_for_multi_grant_vkey",
    "list_proxy_models_for_team",
]
