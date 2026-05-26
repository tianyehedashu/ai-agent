"""MembershipPort：基于 tenancy 成员表的实现。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.infrastructure.repositories.team_repository import TeamMemberRepository
from libs.iam.tenancy import TenantId


class TenancyMembershipAdapter:
    """读取团队成员角色（与 TeamMember 表一致）。"""

    async def member_role(
        self,
        session: AsyncSession,
        *,
        tenant_id: TenantId,
        user_id: uuid.UUID,
    ) -> str | None:
        repo = TeamMemberRepository(session)
        row = await repo.get(uuid.UUID(str(tenant_id)), user_id)
        return row.role if row is not None else None

    async def member_roles_for_user(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
    ) -> dict[TenantId, str]:
        repo = TeamMemberRepository(session)
        by_team = await repo.list_roles_for_user(user_id)
        return {TenantId(team_id): role for team_id, role in by_team.items()}


__all__ = ["TenancyMembershipAdapter"]
