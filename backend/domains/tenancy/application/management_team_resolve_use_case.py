"""管理面团队上下文解析（仅依赖 tenancy 数据与 MembershipPort）。"""

from __future__ import annotations

from contextlib import suppress
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.tenancy.domain.management_context import ManagementTeamContext
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from domains.tenancy.infrastructure.repositories.team_repository import TeamRepository
from libs.exceptions import (
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
)
from libs.iam.tenancy import MembershipPort, TenantId


class TenancyManagementTeamResolveUseCase:
    """JWT 管理面：解析 X-Team-Id / 路径 team_id / personal team 与成员角色。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        membership: MembershipPort | None = None,
    ) -> None:
        self._session = session
        self._teams = TeamRepository(session)
        self._membership = membership or TenancyMembershipAdapter()

    async def resolve_management_team(
        self,
        *,
        user_id: uuid.UUID,
        platform_user_role: str,
        x_team_id: str | None,
        path_team_id: str | None,
    ) -> ManagementTeamContext:
        target_team_id: uuid.UUID | None = None
        if x_team_id:
            with suppress(ValueError):
                target_team_id = uuid.UUID(x_team_id)
        if target_team_id is None and path_team_id:
            with suppress(ValueError):
                target_team_id = uuid.UUID(path_team_id)

        is_platform_admin = platform_user_role == "admin"

        if target_team_id is not None:
            team = await self._teams.get(target_team_id)
            if team is None or not team.is_active:
                raise TeamNotFoundError(str(target_team_id))
            tid = TenantId(team.id)
            if is_platform_admin:
                role = await self._membership.member_role(
                    self._session, tenant_id=tid, user_id=user_id
                )
                role = role if role is not None else "admin"
            else:
                role = await self._membership.member_role(
                    self._session, tenant_id=tid, user_id=user_id
                )
                if role is None:
                    raise TeamPermissionDeniedError(str(team.id))
        else:
            team = await self._teams.get_personal(user_id)
            if team is None:
                raise PersonalTeamNotInitializedError()
            role = "owner"

        return ManagementTeamContext(
            team_id=team.id,
            team_kind=team.kind,
            team_role=role,
            user_id=user_id,
            is_platform_admin=is_platform_admin,
        )


__all__ = ["TenancyManagementTeamResolveUseCase"]
