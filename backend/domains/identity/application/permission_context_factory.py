"""构建带 ``team_ids`` 的 PermissionContext（后台任务 / 无 HTTP 入口）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.domain.anonymous_tenant import (
    anonymous_team_ids,
    normalize_anonymous_cookie_id,
)
from domains.tenancy.application.team_ids_resolver import team_ids_for_user
from libs.iam.permission_context import PermissionContext

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
    normalized_anonymous: str | None = None
    if user_id is not None:
        team_ids = await team_ids_for_user(db, user_id)
    elif anonymous_user_id:
        normalized_anonymous = normalize_anonymous_cookie_id(anonymous_user_id)
        team_ids = anonymous_team_ids(normalized_anonymous)

    ctx = PermissionContext(
        user_id=user_id,
        anonymous_user_id=normalized_anonymous if anonymous_user_id else None,
        role=role,
        team_ids=team_ids,
    )
    if team_id is not None and team_role is not None:
        return ctx.with_team(team_id, team_role)
    return ctx
