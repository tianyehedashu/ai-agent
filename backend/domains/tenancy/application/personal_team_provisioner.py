"""Personal team 幂等创建（封装 TeamService，供 identity/gateway 与迁移回填复用）。"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.application.team_service import TeamService
from domains.tenancy.infrastructure.models.team import Team
from libs.iam.tenancy import TenantId


class PersonalTeamProvisioner:
    def __init__(self, session: AsyncSession) -> None:
        self._teams = TeamService(session)

    async def ensure_personal_team(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str | None = None,
    ) -> uuid.UUID:
        team = await self._teams.ensure_personal_team(user_id, display_name=display_name)
        return team.id

    async def ensure_personal_team_entity(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str | None = None,
    ) -> Team:
        return await self._teams.ensure_personal_team(user_id, display_name=display_name)

    async def as_tenant_id(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str | None = None,
    ) -> TenantId:
        tid = await self.ensure_personal_team(user_id, display_name=display_name)
        return TenantId(tid)


__all__ = ["PersonalTeamProvisioner"]
