"""Admin Users API - 平台用户角色管理。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query

from domains.identity.application.user_use_case import UserSummary, UserUseCase
from domains.identity.domain.policies.platform_role_policy import ANONYMOUS_ROLE
from domains.identity.domain.rbac import Role
from domains.identity.domain.repositories.user_repository import UserListFilters
from domains.identity.presentation.deps import AdminUser
from domains.identity.presentation.schemas import (
    AdminUpdatePlatformUserBody,
    PlatformUserListResponse,
    PlatformUserSummaryResponse,
    SetPlatformRoleBody,
)
from libs.api.pagination import PageParams, page_query_params
from libs.exceptions import NotFoundError
from libs.identity_bridge_deps import get_user_use_case

router = APIRouter()

PageDep = Annotated[PageParams, Depends(page_query_params)]
ASSIGNABLE_ROLES = {Role.ADMIN.value, Role.USER.value, Role.VIEWER.value}


def _to_response(summary: UserSummary) -> PlatformUserSummaryResponse:
    return PlatformUserSummaryResponse(
        id=summary.id,
        email=summary.email,
        name=summary.name,
        role=summary.role,
        is_active=summary.is_active,
        is_verified=summary.is_verified,
        status=summary.status,
        created_at=summary.created_at,
        vendor_creator_id=summary.vendor_creator_id,
        avatar_url=summary.avatar_url,
    )


@router.get("", response_model=PlatformUserListResponse)
async def list_platform_users(
    _: AdminUser,
    page: PageDep,
    user_service: Annotated[UserUseCase, Depends(get_user_use_case)],
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    role: Annotated[str | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> PlatformUserListResponse:
    """分页列出平台用户（默认排除 anonymous）。"""
    if role is not None and role not in ASSIGNABLE_ROLES:
        role = None
    filters = UserListFilters(
        search=search.strip() if search else None,
        role=role,
        is_active=is_active,
    )
    result = await user_service.list_users_page(page, filters)
    return PlatformUserListResponse(
        items=[_to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
        has_prev=result.has_prev,
    )


@router.get("/lookup", response_model=PlatformUserSummaryResponse)
async def lookup_user_by_email(
    _: AdminUser,
    email: Annotated[str, Query(min_length=3, max_length=320)],
    user_service: Annotated[UserUseCase, Depends(get_user_use_case)],
) -> PlatformUserSummaryResponse:
    """按邮箱查找已注册用户（平台管理员）。"""
    summary = await user_service.lookup_user_by_email(email)
    return _to_response(summary)


@router.get("/{user_id}", response_model=PlatformUserSummaryResponse)
async def get_platform_user(
    user_id: uuid.UUID,
    _: AdminUser,
    user_service: Annotated[UserUseCase, Depends(get_user_use_case)],
) -> PlatformUserSummaryResponse:
    """获取单个平台用户详情。"""
    summary = await user_service.get_user_summary(str(user_id))
    if summary.role == ANONYMOUS_ROLE:
        raise NotFoundError("User", str(user_id))
    return _to_response(summary)


@router.patch("/{user_id}", response_model=PlatformUserSummaryResponse)
async def update_platform_user(
    user_id: uuid.UUID,
    body: AdminUpdatePlatformUserBody,
    admin: AdminUser,
    user_service: Annotated[UserUseCase, Depends(get_user_use_case)],
) -> PlatformUserSummaryResponse:
    """更新用户资料与启用状态（平台管理员）。"""
    summary = await user_service.admin_update_user(
        actor_id=admin.id,
        actor_role=admin.role,
        target_user_id=str(user_id),
        name=body.name,
        avatar_url=body.avatar_url,
        vendor_creator_id=body.vendor_creator_id,
        update_vendor_creator_id="vendor_creator_id" in body.model_fields_set,
        is_active=body.is_active,
    )
    return _to_response(summary)


@router.patch("/{user_id}/role", response_model=PlatformUserSummaryResponse)
async def set_user_platform_role(
    user_id: uuid.UUID,
    body: SetPlatformRoleBody,
    admin: AdminUser,
    user_service: Annotated[UserUseCase, Depends(get_user_use_case)],
) -> PlatformUserSummaryResponse:
    """设置用户的平台角色（平台管理员）。"""
    summary = await user_service.set_platform_role(
        actor_id=admin.id,
        actor_role=admin.role,
        target_user_id=str(user_id),
        new_role=body.role,
    )
    return _to_response(summary)
