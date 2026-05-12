"""TeamService - 团队管理（personal team 自动创建）"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.models.team import Team, TeamMember
from domains.gateway.infrastructure.repositories.team_repository import (
    TeamMemberRepository,
    TeamRepository,
)


class TeamService:
    """团队管理"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._teams = TeamRepository(session)
        self._members = TeamMemberRepository(session)

    async def ensure_personal_team(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str | None = None,
    ) -> Team:
        """确保该用户有 personal team，没有则创建（注册流程使用）"""
        existing = await self._teams.get_personal(user_id)
        if existing is not None:
            return existing
        team = await self._teams.create(
            name=display_name or "Personal",
            slug=f"personal-{user_id}",
            kind="personal",
            owner_user_id=user_id,
            settings={},
        )
        await self._members.add(team.id, user_id, role="owner")
        return team

    async def create_team(
        self,
        *,
        name: str,
        owner_user_id: uuid.UUID,
        slug: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Team:
        team = await self._teams.create(
            name=name,
            slug=slug or f"team-{uuid.uuid4().hex[:8]}",
            kind="shared",
            owner_user_id=owner_user_id,
            settings=settings,
        )
        await self._members.add(team.id, owner_user_id, role="owner")
        return team

    async def add_member(
        self, team_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> TeamMember:
        existing = await self._members.get(team_id, user_id)
        if existing is not None:
            return await self._members.update_role(team_id, user_id, role) or existing
        return await self._members.add(team_id, user_id, role)

    async def remove_member(self, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        team = await self._teams.get(team_id)
        if team is None:
            return False
        # 不允许移除 personal team 的 owner
        if team.kind == "personal" and team.owner_user_id == user_id:
            raise ValueError("Cannot remove owner from personal team")
        return await self._members.remove(team_id, user_id)

    async def list_user_teams(self, user_id: uuid.UUID) -> list[Team]:
        return await self._teams.list_for_user(user_id)

    async def get_team(self, team_id: uuid.UUID) -> Team | None:
        """按 id 读取团队（供管理面查询）"""
        return await self._teams.get(team_id)

    async def update_team(
        self,
        team_id: uuid.UUID,
        *,
        name: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> Team | None:
        return await self._teams.update(team_id, name=name, settings=settings)

    async def delete_shared_team(self, team_id: uuid.UUID) -> None:
        team = await self._teams.get(team_id)
        if team is None:
            return
        if team.kind == "personal":
            raise ValueError("Cannot delete personal team")
        await self._teams.delete(team_id)


__all__ = ["TeamService"]
