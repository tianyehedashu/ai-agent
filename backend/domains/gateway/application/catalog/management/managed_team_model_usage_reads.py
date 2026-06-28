"""跨团队可管理模型用量聚合（actor 维度）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.domain.credential.managed_team_credentials_policy import WritableTeamSnapshot
from domains.gateway.domain.visibility.managed_team_resource_policy import (
    build_managed_team_readable_resource_list_plan,
)
from domains.tenancy.application.team_service import TeamService
from domains.tenancy.domain.management_context import ManagementTeamContext
from libs.api.pagination import slice_page

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def aggregate_managed_team_models_route_usage(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    days: int,
    provider: str | None = None,
    route_names: list[str] | None = None,
    team_search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict[str, Any]], int, datetime, datetime]:
    """按可管理团队逐 tenant 聚合 route 用量；items 含 ``team_id``。"""
    reads = GatewayManagementReadService(session)
    listing = TeamService(session)
    memberships = await listing.list_gateway_team_memberships(
        user_id,
        is_platform_admin=is_platform_admin,
        search=team_search,
    )
    snapshots = [
        WritableTeamSnapshot(team_id=m.team_id, kind=m.kind, role=m.role) for m in memberships
    ]
    plan = build_managed_team_readable_resource_list_plan(
        snapshots,
        is_platform_admin=is_platform_admin,
    )
    allowed_tenant_ids = set(plan.tenant_ids)
    tenant_ids = list(plan.tenant_ids)
    role_by_tenant = {m.team_id: m.role for m in memberships if m.team_id in allowed_tenant_ids}
    kind_by_tenant = {m.team_id: m.kind for m in memberships if m.team_id in allowed_tenant_ids}

    if not tenant_ids:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
        return [], 0, start, end

    all_items: list[dict[str, Any]] = []
    start: datetime | None = None
    end: datetime | None = None

    for tenant_id in tenant_ids:
        ctx = ManagementTeamContext(
            team_id=tenant_id,
            team_kind=kind_by_tenant.get(tenant_id, "shared"),
            team_role=role_by_tenant.get(tenant_id, "member"),
            user_id=user_id,
            is_platform_admin=is_platform_admin,
        )
        items, _total, item_start, item_end = await reads.aggregate_gateway_model_route_usage(
            ctx,
            days=days,
            provider=provider,
            route_names=route_names,
            page=1,
            page_size=10_000,
        )
        if start is None:
            start = item_start
            end = item_end
        for row in items:
            all_items.append({**row, "team_id": tenant_id})

    if route_names is not None:
        route_set = set(route_names)
        filtered = [i for i in all_items if i["route_name"] in route_set]
        total = len(filtered)
        if start is None or end is None:
            end = datetime.now(UTC)
            start = end - timedelta(days=days)
        return filtered, total, start, end

    all_items.sort(key=lambda i: (str(i["team_id"]), i["route_name"]))
    page_items, total = slice_page(all_items, page=page, page_size=page_size)
    if start is None or end is None:
        end = datetime.now(UTC)
        start = end - timedelta(days=days)
    return page_items, total, start, end


__all__ = ["aggregate_managed_team_models_route_usage"]
