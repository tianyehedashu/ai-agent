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


__all__ = ["TenancyMembershipAdapter"]
