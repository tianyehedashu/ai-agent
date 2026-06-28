"""Actor-scoped managed team virtual keys aggregate list."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.vkey.management.managed_team_virtual_key_reads import (
    list_managed_team_virtual_keys_for_actor,
    list_managed_team_vkey_entitlements_for_actor,
)
from domains.gateway.presentation.plan_response import entitlement_plan_to_response
from domains.gateway.presentation.routers._common import vkey_to_response
from domains.gateway.presentation.schemas.common import (
    ManagedTeamVirtualKeyListResponse,
    ManagedTeamVkeyEntitlementItem,
    ManagedTeamVkeyEntitlementsResponse,
)
from domains.identity.domain.rbac import Role
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.api.pagination import PageParams, build_page, page_query_params
from libs.db.database import get_db

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]
PageDep = Annotated[PageParams, Depends(page_query_params)]


@router.get("/managed-team-keys", response_model=ManagedTeamVirtualKeyListResponse)
async def list_managed_team_virtual_keys(
    current_user: RequiredAuthUser,
    db: DbSession,
    page: PageDep,
) -> ManagedTeamVirtualKeyListResponse:
    """列出当前用户 membership 内各团队下自建的虚拟 Key（跨团队聚合，分页）。"""
    is_platform_admin = current_user.role == Role.ADMIN.value
    result = await list_managed_team_virtual_keys_for_actor(
        db,
        user_id=get_user_uuid(current_user),
        is_platform_admin=is_platform_admin,
        page_params=page,
    )
    envelope = build_page(
        items=[vkey_to_response(row) for row in result.page_items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )
    return ManagedTeamVirtualKeyListResponse(
        **envelope.model_dump(),
        queried_team_count=result.queried_team_count,
        queried_personal_team_count=result.queried_personal_team_count,
        queried_shared_team_count=result.queried_shared_team_count,
        tenant_ids_with_keys=list(result.tenant_ids_with_keys),
    )


@router.get(
    "/managed-team-vkey-entitlements",
    response_model=ManagedTeamVkeyEntitlementsResponse,
)
async def list_managed_team_vkey_entitlements(
    current_user: RequiredAuthUser,
    db: DbSession,
) -> ManagedTeamVkeyEntitlementsResponse:
    """当前用户可见 vkey 的客户套餐（单次批量，供虚拟 Key 列表页使用）。"""
    is_platform_admin = current_user.role == Role.ADMIN.value
    result = await list_managed_team_vkey_entitlements_for_actor(
        db,
        user_id=get_user_uuid(current_user),
        is_platform_admin=is_platform_admin,
    )
    items = [
        ManagedTeamVkeyEntitlementItem(
            vkey_id=vkey_id,
            plans=[entitlement_plan_to_response(plan) for plan in plans],
        )
        for vkey_id, plans in sorted(result.entitlements_by_vkey_id.items(), key=lambda x: x[0])
    ]
    return ManagedTeamVkeyEntitlementsResponse(items=items)
