"""Admin Users API - 平台用户角色管理。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query

from domains.identity.application.user_use_case import UserSummary, UserUseCase
from domains.identity.presentation.deps import AdminUser
from domains.identity.presentation.schemas import (
    PlatformUserSummaryResponse,
    SetPlatformRoleBody,
)
from libs.identity_bridge_deps import get_user_use_case

router = APIRouter()


def _to_response(summary: UserSummary) -> PlatformUserSummaryResponse:
    return PlatformUserSummaryResponse(
        id=summary.id,
        email=summary.email,
        name=summary.name,
        role=summary.role,
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
