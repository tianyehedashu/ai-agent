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

from domains.identity.presentation.deps import (
    RequiredAuthUser,
    VIEWER_ROLE,
    get_current_user,
)
from domains.identity.presentation.schemas import CurrentUser
from domains.tenancy.application.management_team_resolve_use_case import (
    TenancyManagementTeamResolveUseCase,
)
from domains.tenancy.domain.management_context import ManagementTeamContext
from domains.tenancy.domain.policies.team_role import (
    TeamRole,
    assert_gateway_admin,
    assert_team_role,
)
from libs.db.database import get_db
from libs.iam.permission_context import merge_team_into_permission_context, get_permission_context
from libs.exceptions import (
    PermissionDeniedError,
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
)
from libs.iam.team_http import map_team_access_exception_to_http

ResolvedTeam = ManagementTeamContext

_GATEWAY_READ_ONLY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def merge_optional_gateway_team(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    platform_user_role: str,
    team_id: uuid.UUID | None,
) -> None:
    """将显式 team_id 写入 PermissionContext（Chat 等无路径团队入口）。"""
    if team_id is None:
        return
    if get_permission_context() is None:
        return
    resolver = TenancyManagementTeamResolveUseCase(db)
    try:
        resolved = await resolver.resolve_management_team(
            user_id=user_id,
            platform_user_role=platform_user_role,
            x_team_id=None,
            path_team_id=str(team_id),
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
    merge_team_into_permission_context(
        team_id=resolved.team_id,
        team_role=resolved.team_role,
    )


def _assert_gateway_not_viewer_write(request: Request, platform_role: str) -> None:
    if platform_role != VIEWER_ROLE:
        return
    if request.method in _GATEWAY_READ_ONLY_METHODS:
        return
    raise PermissionDeniedError(
        message="Viewer accounts are read-only on AI Gateway",
        resource="AI Gateway",
    )


async def resolve_current_team(
    request: Request,
    current_user: RequiredAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_team_id: Annotated[str | None, Header(alias="X-Team-Id")] = None,
) -> ManagementTeamContext:
    """解析当前团队：路径 team_id > X-Team-Id > personal team。匿名 401。"""
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous users cannot access AI Gateway",
        )
    try:
        _assert_gateway_not_viewer_write(request, current_user.role)
    except PermissionDeniedError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

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

    merge_team_into_permission_context(
        team_id=resolved.team_id,
        team_role=resolved.team_role,
    )

    return resolved


CurrentTeam = Annotated[ManagementTeamContext, Depends(resolve_current_team)]


async def attach_optional_team_from_header(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_team_id: Annotated[str | None, Header(alias="X-Team-Id")] = None,
) -> None:
    """将 ``X-Team-Id`` 写入 ``PermissionContext``，供内部 Gateway 桥接按当前团队归账。

    未带头或匿名会话时不修改上下文（桥接仍用 personal team）。
    解析与成员校验与 ``resolve_current_team`` 一致。
    """
    if current_user.is_anonymous:
        return
    trimmed = (x_team_id or "").strip()
    if not trimmed:
        return
    user_id = uuid.UUID(current_user.id)
    resolver = TenancyManagementTeamResolveUseCase(db)
    try:
        resolved = await resolver.resolve_management_team(
            user_id=user_id,
            platform_user_role=current_user.role,
            x_team_id=trimmed,
            path_team_id=None,
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

    merge_team_into_permission_context(
        team_id=resolved.team_id,
        team_role=resolved.team_role,
    )


AttachOptionalTeamContext = Annotated[None, Depends(attach_optional_team_from_header)]


def _require_team_role(*roles: str):
    """工厂：要求当前团队角色 ∈ roles 或者平台 admin"""

    async def _dep(team: CurrentTeam) -> ManagementTeamContext:
        try:
            assert_team_role(team, *roles)
        except TeamPermissionDeniedError as exc:
            http_exc = map_team_access_exception_to_http(exc)
            if http_exc is None:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unmapped team access error",
                ) from exc
            raise http_exc from exc
        return team

    return _dep


async def require_team_member(team: CurrentTeam) -> ManagementTeamContext:
    return team


async def require_team_admin(
    team: ManagementTeamContext = Depends(
        _require_team_role(TeamRole.OWNER.value, TeamRole.ADMIN.value)
    ),
) -> ManagementTeamContext:
    return team


async def require_team_owner(
    team: ManagementTeamContext = Depends(_require_team_role(TeamRole.OWNER.value)),
) -> ManagementTeamContext:
    return team


async def require_gateway_admin(
    team: CurrentTeam,
) -> ManagementTeamContext:
    """平台 admin 或 团队 owner/admin"""
    try:
        assert_gateway_admin(team)
    except TeamPermissionDeniedError as exc:
        http_exc = map_team_access_exception_to_http(exc)
        if http_exc is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unmapped team access error",
            ) from exc
        raise http_exc from exc
    return team


RequiredTeamMember = Annotated[ManagementTeamContext, Depends(require_team_member)]
RequiredTeamAdmin = Annotated[ManagementTeamContext, Depends(require_team_admin)]
RequiredTeamOwner = Annotated[ManagementTeamContext, Depends(require_team_owner)]
RequiredGatewayAdmin = Annotated[ManagementTeamContext, Depends(require_gateway_admin)]


__all__ = [
    "AttachOptionalTeamContext",
    "CurrentTeam",
    "RequiredGatewayAdmin",
    "RequiredTeamAdmin",
    "RequiredTeamMember",
    "RequiredTeamOwner",
    "ResolvedTeam",
    "attach_optional_team_from_header",
    "merge_optional_gateway_team",
    "resolve_current_team",
]
