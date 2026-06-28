"""跨团队 membership 虚拟 Key 聚合读侧（actor 维度）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.quota.management.plan_read_mappers import entitlement_plan_from_orm
from domains.gateway.application.quota.management.plan_read_model import EntitlementPlanReadModel
from domains.gateway.domain.vkey.virtual_key_access import filter_virtual_keys_visible_to_actor
from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    EntitlementPlanRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository
from domains.tenancy.application.ports import GatewayTeamListingPort
from domains.tenancy.application.team_service import TeamService
from libs.api.pagination import PageParams

from .virtual_key_read_mappers import (
    virtual_keys_from_orm_with_grants,
)
from .virtual_key_read_model import VirtualKeyReadModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ManagedTeamVirtualKeyListPage:
    page_items: tuple[VirtualKeyReadModel, ...]
    total: int
    page: int
    page_size: int
    queried_team_count: int
    queried_personal_team_count: int
    queried_shared_team_count: int
    tenant_ids_with_keys: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class ManagedTeamVkeyEntitlementsPage:
    entitlements_by_vkey_id: dict[uuid.UUID, tuple[EntitlementPlanReadModel, ...]]


async def _membership_counts(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    team_listing: GatewayTeamListingPort | None,
) -> tuple[list[uuid.UUID], int, int, int]:
    listing = team_listing or TeamService(session)
    memberships = await listing.list_gateway_team_memberships(
        user_id,
        is_platform_admin=is_platform_admin,
        search=None,
    )
    tenant_ids = [m.team_id for m in memberships]
    personal_count = sum(1 for m in memberships if m.kind == "personal")
    shared_count = sum(1 for m in memberships if m.kind == "shared")
    return tenant_ids, len(tenant_ids), personal_count, shared_count


async def list_managed_team_virtual_keys_for_actor(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    page_params: PageParams,
    team_listing: GatewayTeamListingPort | None = None,
) -> ManagedTeamVirtualKeyListPage:
    """列出当前用户 membership 内各团队下自建的虚拟 Key（含 personal + 协作团队）。"""
    tenant_ids, queried_team_count, personal_count, shared_count = await _membership_counts(
        session,
        user_id=user_id,
        is_platform_admin=is_platform_admin,
        team_listing=team_listing,
    )

    repo = VirtualKeyRepository(session)
    total = await repo.count_non_system_active_for_tenants(
        tenant_ids,
        created_by_user_id=user_id,
    )
    # SQL 预筛 created_by；domain filter 与 list/reveal/revoke 共用 virtual_key_access 语义。
    rows = await repo.list_non_system_active_for_tenants(
        tenant_ids,
        created_by_user_id=user_id,
        offset=page_params.offset,
        limit=page_params.page_size,
    )
    filtered = filter_virtual_keys_visible_to_actor(rows, actor_user_id=user_id)
    page_items = await virtual_keys_from_orm_with_grants(session, filtered)
    tenant_ids_with_keys = tuple(
        await repo.list_distinct_tenant_ids_with_non_system_active_keys(
            tenant_ids,
            created_by_user_id=user_id,
        )
    )
    return ManagedTeamVirtualKeyListPage(
        page_items=tuple(page_items),
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
        queried_team_count=queried_team_count,
        queried_personal_team_count=personal_count,
        queried_shared_team_count=shared_count,
        tenant_ids_with_keys=tenant_ids_with_keys,
    )


async def list_managed_team_vkey_entitlements_for_actor(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    team_listing: GatewayTeamListingPort | None = None,
) -> ManagedTeamVkeyEntitlementsPage:
    """当前用户可见 vkey 的客户套餐（批量，消除列表页 N+1）。"""
    tenant_ids, _, _, _ = await _membership_counts(
        session,
        user_id=user_id,
        is_platform_admin=is_platform_admin,
        team_listing=team_listing,
    )
    vkey_repo = VirtualKeyRepository(session)
    vkey_ids = await vkey_repo.list_non_system_active_ids_for_tenants(
        tenant_ids,
        created_by_user_id=user_id,
    )
    if not vkey_ids:
        return ManagedTeamVkeyEntitlementsPage(entitlements_by_vkey_id={})

    ent_repo = EntitlementPlanRepository(session)
    rows_by_vkey = await ent_repo.list_with_quotas_for_vkeys(vkey_ids)
    entitlements_by_vkey_id = {
        vkey_id: tuple(entitlement_plan_from_orm(plan, quotas) for plan, quotas in plan_rows)
        for vkey_id, plan_rows in rows_by_vkey.items()
    }
    return ManagedTeamVkeyEntitlementsPage(entitlements_by_vkey_id=entitlements_by_vkey_id)


__all__ = [
    "ManagedTeamVirtualKeyListPage",
    "ManagedTeamVkeyEntitlementsPage",
    "list_managed_team_virtual_keys_for_actor",
    "list_managed_team_vkey_entitlements_for_actor",
]
