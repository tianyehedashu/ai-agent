"""团队成员查询（供 identity 等域填充 PermissionContext.team_ids）。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.infrastructure.models.team import TeamMember


async def list_team_ids_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> frozenset[uuid.UUID]:
    """返回用户可访问的 tenant_id（team_members.team_id）集合。"""
    stmt = select(TeamMember.team_id).where(TeamMember.user_id == user_id)
    result = await session.execute(stmt)
    return frozenset(result.scalars().all())


__all__ = ["list_team_ids_for_user"]
