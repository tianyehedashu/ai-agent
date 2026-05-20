"""构建带 ``team_ids`` 的 PermissionContext（后台任务 / 无 HTTP 入口）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.anonymous_user_provisioner import AnonymousUserProvisioner
from domains.tenancy.application.team_membership_queries import list_team_ids_for_user
from libs.db.permission_context import PermissionContext

__all__ = ["build_permission_context_with_team_ids"]


async def build_permission_context_with_team_ids(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    anonymous_user_id: str | None,
    role: str = "user",
    team_id: uuid.UUID | None = None,
    team_role: str | None = None,
) -> PermissionContext:
    """解析 ``team_members`` 并返回完整 PermissionContext。"""
    team_ids: frozenset[uuid.UUID] = frozenset()
    if user_id is not None:
        team_ids = await list_team_ids_for_user(db, user_id)
    elif anonymous_user_id:
        shadow_id = await AnonymousUserProvisioner(db).ensure_shadow_user(anonymous_user_id)
        team_ids = await list_team_ids_for_user(db, shadow_id)

    ctx = PermissionContext(
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        role=role,
        team_ids=team_ids,
    )
    if team_id is not None and team_role is not None:
        return ctx.with_team(team_id, team_role)
    return ctx
