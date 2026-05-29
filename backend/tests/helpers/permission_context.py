"""测试用 PermissionContext 装配（含 team_ids）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.permission_context_factory import (
    build_permission_context_with_team_ids,
)
from libs.iam.permission_context import PermissionContext


async def permission_context_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    role: str = "user",
) -> PermissionContext:
    """与生产 ``build_permission_context_with_team_ids`` 一致。"""
    return await build_permission_context_with_team_ids(
        db,
        user_id=user_id,
        role=role,
    )
