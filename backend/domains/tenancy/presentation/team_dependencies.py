"""
Tenancy 管理面团队依赖（/api/v1/gateway/* 团队上下文）

解析逻辑在 ``TenancyManagementTeamResolveUseCase``，成员角色仅经 ``MembershipPort``。
HTTP 映射经 ``libs.iam.team_http``；团队路由仅使用 ``TeamService``，不依赖 ``domains.gateway``。
"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.presentation.deps import RequiredAuthUser
from domains.tenancy.application.management_team_resolve_use_case import (
    TenancyManagementTeamResolveUseCase,
)
from domains.tenancy.domain.management_context import ManagementTeamContext
from libs.db.database import get_db
from libs.db.permission_context import PermissionContext, set_permission_context
from libs.exceptions import (
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
)
from libs.iam.team_http import map_team_access_exception_to_http

__all__ = [
    "CurrentTeam",
    "RequiredGatewayAdmin",
    "RequiredTeamAdmin",
    "RequiredTeamMember",
    "RequiredTeamOwner",
    "ResolvedTeam",
    "resolve_current_team",
]

ResolvedTeam = ManagementTeamContext


async def resolve_current_team(
    request: Request,
    current_user: RequiredAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_team_id: Annotated[str | None, Header(alias="X-Team-Id")] = None,
) -> ManagementTeamContext:
    """解析当前团队：X-Team-Id > 路径 team_id > personal team。匿名 401。"""
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous users cannot access AI Gateway",
        )

    user_id = uuid.UUID(current_user.id)
    path_raw = request.path_params.get("team_id")
    path_team_id = path_raw if isinstance(path_raw, str) else None

    resolver = TenancyManagementTeamResolveUseCase(db)
    try:
        resolved = await resolver.resolve_management_team(
            user_id=user_id,
            platform_user_role=current_user.role,
            x_team_id=x_team_id,
            path_team_id=path_team_id,
        )
    except (
        TeamNotFoundError,
        TeamPermissionDeniedError,
        PersonalTeamNotInitializedError,
    ) as exc:
        http_exc = map_team_access_exception_to_http(exc)
        if http_exc is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unmapped team access error",
            ) from exc
        raise http_exc from exc

    set_permission_context(
        PermissionContext(
            user_id=user_id,
            anonymous_user_id=None,
            role=current_user.role,
            team_id=resolved.team_id,
            team_role=resolved.team_role,
        )
    )

    return resolved


CurrentTeam = Annotated[ManagementTeamContext, Depends(resolve_current_team)]


def _require_team_role(*roles: str):
    """工厂：要求当前团队角色 ∈ roles 或者平台 admin"""

    async def _dep(team: CurrentTeam) -> ManagementTeamContext:
        if team.is_platform_admin:
            return team
        if team.team_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required team role: {', '.join(roles)}",
            )
        return team

    return _dep


async def require_team_member(team: CurrentTeam) -> ManagementTeamContext:
    return team


async def require_team_admin(
    team: ManagementTeamContext = Depends(_require_team_role("owner", "admin")),
) -> ManagementTeamContext:
    return team


async def require_team_owner(
    team: ManagementTeamContext = Depends(_require_team_role("owner")),
) -> ManagementTeamContext:
    return team


async def require_gateway_admin(
    current_user: RequiredAuthUser,
    team: CurrentTeam,
) -> ManagementTeamContext:
    """平台 admin 或 团队 owner/admin"""
    if current_user.role == "admin":
        return team
    if team.team_role in {"owner", "admin"}:
        return team
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Required role: platform admin or team admin/owner",
    )


RequiredTeamMember = Annotated[ManagementTeamContext, Depends(require_team_member)]
RequiredTeamAdmin = Annotated[ManagementTeamContext, Depends(require_team_admin)]
RequiredTeamOwner = Annotated[ManagementTeamContext, Depends(require_team_owner)]
RequiredGatewayAdmin = Annotated[ManagementTeamContext, Depends(require_gateway_admin)]
