"""测试用 PermissionContext 装配（含 team_ids）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.anonymous_user_provisioner import AnonymousUserProvisioner
from domains.tenancy.application.team_ids_resolver import team_ids_for_user
from libs.iam.permission_context import PermissionContext


async def permission_context_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    anonymous_user_id: str | None = None,
    role: str = "user",
) -> PermissionContext:
    """与生产 ``build_permission_context_with_team_ids`` 一致。"""
    resolved_user_id = user_id
    if resolved_user_id is None and anonymous_user_id:
        resolved_user_id = await AnonymousUserProvisioner(db).ensure_shadow_user(
            anonymous_user_id
        )
    team_ids: frozenset[uuid.UUID] = frozenset()
    if resolved_user_id is not None:
        team_ids = await team_ids_for_user(db, resolved_user_id)
    return PermissionContext(
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        role=role,
        team_ids=team_ids,
    )
