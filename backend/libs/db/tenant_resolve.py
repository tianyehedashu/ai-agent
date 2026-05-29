"""从 PermissionContext 解析写入用 tenant_id。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from libs.iam.data_scope_policy import require_permission_context


async def resolve_tenant_id_for_write(db: AsyncSession) -> uuid.UUID:
    """活动团队优先，否则 personal team。"""
    ctx = require_permission_context()
    if ctx.team_id is not None:
        return ctx.team_id
    if ctx.user_id is not None:
        return await PersonalTeamProvisioner(db).ensure_personal_team(ctx.user_id)
    msg = "Cannot resolve tenant_id without user identity in PermissionContext"
    raise RuntimeError(msg)


__all__ = ["resolve_tenant_id_for_write"]
