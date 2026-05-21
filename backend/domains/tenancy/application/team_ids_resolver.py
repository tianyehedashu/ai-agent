"""解析用户可见 team_id 集合（personal + memberships）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from domains.tenancy.application.team_membership_queries import list_team_ids_for_user

__all__ = ["team_ids_for_user"]


async def team_ids_for_user(db: AsyncSession, user_id: uuid.UUID) -> frozenset[uuid.UUID]:
    """personal team 与 ``team_members`` 成员关系的并集。"""
    personal = await PersonalTeamProvisioner(db).ensure_personal_team(user_id)
    memberships = await list_team_ids_for_user(db, user_id)
    return frozenset(memberships) | {personal}
