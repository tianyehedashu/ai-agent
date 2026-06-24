"""虚拟路由 owner 的 slug 前缀解析上下文（与 personal 写侧 grant slug 对齐）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.vkey_team_resolution import fetch_grant_team_slug_rows
from domains.gateway.domain.vkey_grant_slug_policy import build_unique_slug_to_tenant_id
from domains.tenancy.application.team_service import TeamService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class RouteOwnerSlugContext:
    """路由所属 tenant 解析 ``primary_models`` 引用时的 slug 上下文。"""

    slug_to_tenant: dict[str, uuid.UUID]
    enable_slug_prefix: bool


async def build_route_owner_slug_context(
    session: AsyncSession,
    route_owner_tenant_id: uuid.UUID | None,
) -> RouteOwnerSlugContext:
    """单条路由 owner 的 slug 上下文（personal 才启用 grant slug 前缀）。"""
    if route_owner_tenant_id is None:
        return RouteOwnerSlugContext(slug_to_tenant={}, enable_slug_prefix=False)
    teams = TeamService(session)
    team = await teams.get_team(route_owner_tenant_id)
    if team is None or team.kind != "personal":
        return RouteOwnerSlugContext(slug_to_tenant={}, enable_slug_prefix=False)
    return await _personal_owner_slug_context(session, team.id, team.owner_user_id)


async def build_route_owner_slug_contexts(
    session: AsyncSession,
    route_owner_tenant_ids: frozenset[uuid.UUID],
) -> dict[uuid.UUID, RouteOwnerSlugContext]:
    """批量构建路由 owner slug 上下文（Router 重建等热路径）。"""
    if not route_owner_tenant_ids:
        return {}
    teams = TeamService(session)
    contexts: dict[uuid.UUID, RouteOwnerSlugContext] = {}
    owner_maps: dict[uuid.UUID, dict[str, uuid.UUID]] = {}
    for tenant_id in route_owner_tenant_ids:
        team = await teams.get_team(tenant_id)
        if team is None:
            contexts[tenant_id] = RouteOwnerSlugContext(slug_to_tenant={}, enable_slug_prefix=False)
            continue
        if team.kind != "personal":
            contexts[tenant_id] = RouteOwnerSlugContext(slug_to_tenant={}, enable_slug_prefix=False)
            continue
        owner_id = team.owner_user_id
        if owner_id not in owner_maps:
            memberships = await teams.list_gateway_team_memberships(
                owner_id,
                is_platform_admin=False,
            )
            membership_ids = tuple(m.team_id for m in memberships)
            slug_rows = await fetch_grant_team_slug_rows(session, membership_ids)
            owner_maps[owner_id] = build_unique_slug_to_tenant_id(slug_rows)
        contexts[tenant_id] = RouteOwnerSlugContext(
            slug_to_tenant=owner_maps[owner_id],
            enable_slug_prefix=True,
        )
    return contexts


async def _personal_owner_slug_context(
    session: AsyncSession,
    personal_team_id: uuid.UUID,
    owner_user_id: uuid.UUID,
) -> RouteOwnerSlugContext:
    teams = TeamService(session)
    memberships = await teams.list_gateway_team_memberships(
        owner_user_id,
        is_platform_admin=False,
    )
    membership_ids = tuple(m.team_id for m in memberships)
    slug_rows = await fetch_grant_team_slug_rows(session, membership_ids)
    return RouteOwnerSlugContext(
        slug_to_tenant=build_unique_slug_to_tenant_id(slug_rows),
        enable_slug_prefix=True,
    )


__all__ = [
    "RouteOwnerSlugContext",
    "build_route_owner_slug_context",
    "build_route_owner_slug_contexts",
]
