"""管理面团队上下文安装（解析 + 写入 PermissionContext）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.application.management_team_resolve_use_case import (
    TenancyManagementTeamResolveUseCase,
)
from domains.tenancy.domain.management_context import ManagementTeamContext
from libs.iam.permission_context import (
    get_permission_context,
    merge_team_into_permission_context,
)


async def install_management_team_context(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    platform_user_role: str,
    path_team_id: str | None = None,
    x_team_id: str | None = None,
) -> ManagementTeamContext:
    """解析团队并 merge 到当前 PermissionContext（须已由认证依赖安装）。"""
    ctx = get_permission_context()
    if ctx is None:
        msg = "PermissionContext must be set before install_management_team_context"
        raise RuntimeError(msg)

    resolved = await TenancyManagementTeamResolveUseCase(session).resolve_management_team(
        user_id=user_id,
        platform_user_role=platform_user_role,
        x_team_id=x_team_id,
        path_team_id=path_team_id,
    )
    merge_team_into_permission_context(
        team_id=resolved.team_id,
        team_role=resolved.team_role,
    )
    return resolved


__all__ = ["install_management_team_context"]
