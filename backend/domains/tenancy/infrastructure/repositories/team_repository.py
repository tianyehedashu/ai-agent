"""TeamRepository / TeamMemberRepository（租户权威数据访问）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select

from domains.tenancy.infrastructure.models.team import Team, TeamMember

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class TeamRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, team_id: uuid.UUID) -> Team | None:
        return await self._session.get(Team, team_id)

    async def get_by_ids(self, team_ids: list[uuid.UUID]) -> list[Team]:
        if not team_ids:
            return []
        stmt = select(Team).where(Team.id.in_(team_ids))
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_display_names_by_ids(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        """批量解析团队展示名（供跨域读模型标签等）。"""
        if not team_ids:
            return {}
        stmt = select(Team.id, Team.name).where(Team.id.in_(team_ids))
        rows = (await self._session.execute(stmt)).all()
        out: dict[uuid.UUID, str] = {}
        for tid, name in rows:
            out[tid] = name
        return out

    async def get_personal(self, user_id: uuid.UUID) -> Team | None:
        """返回该用户的活跃 personal team（至多一条，见 partial unique index）。

        使用 ``ORDER BY ... LIMIT 1`` 而非 ``scalar_one_or_none()``，避免在约束
        尚未生效或历史脏数据下因多行抛 ``MultipleResultsFound``。
        """
        stmt = (
            select(Team)
            .where(
                Team.owner_user_id == user_id,
                Team.kind == "personal",
                Team.is_active.is_(True),
            )
            .order_by(Team.created_at.asc(), Team.id.asc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Team]:
        """列出用户加入的所有团队（含 personal + shared）"""
        stmt = (
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(
                TeamMember.user_id == user_id,
                Team.is_active.is_(True),
            )
            .order_by(Team.kind.desc(), Team.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_all_active(self) -> list[Team]:
        """列出全部活跃团队（平台 admin Gateway 管理面）。"""
        stmt = (
            select(Team).where(Team.is_active.is_(True)).order_by(Team.kind.desc(), Team.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        name: str,
        slug: str,
        kind: str,
        owner_user_id: uuid.UUID,
        settings: dict[str, Any] | None = None,
    ) -> Team:
        team = Team(
            name=name,
            slug=slug,
            kind=kind,
            owner_user_id=owner_user_id,
            settings=settings,
            is_active=True,
        )
        self._session.add(team)
        await self._session.flush()
        return team

    async def update(
        self,
        team_id: uuid.UUID,
        *,
        name: str | None = None,
        settings: dict[str, Any] | None = None,
        is_active: bool | None = None,
    ) -> Team | None:
        team = await self.get(team_id)
        if team is None:
            return None
        if name is not None:
            team.name = name
        if settings is not None:
            team.settings = settings
        if is_active is not None:
            team.is_active = is_active
        await self._session.flush()
        return team

    async def delete(self, team_id: uuid.UUID) -> bool:
        team = await self.get(team_id)
        if team is None:
            return False
        await self._session.delete(team)
        await self._session.flush()
        return True


class TeamMemberRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, team_id: uuid.UUID, user_id: uuid.UUID) -> TeamMember | None:
        stmt = select(TeamMember).where(
            and_(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_team(self, team_id: uuid.UUID) -> list[TeamMember]:
        stmt = (
            select(TeamMember)
            .where(TeamMember.team_id == team_id)
            .order_by(TeamMember.role, TeamMember.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_roles_for_user(self, user_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """单次查询用户全部 team_id → role（Gateway 团队列表避免 N+1）。"""
        stmt = select(TeamMember.team_id, TeamMember.role).where(TeamMember.user_id == user_id)
        result = await self._session.execute(stmt)
        return dict(result.all())

    async def add(self, team_id: uuid.UUID, user_id: uuid.UUID, role: str) -> TeamMember:
        member = TeamMember(team_id=team_id, user_id=user_id, role=role)
        self._session.add(member)
        await self._session.flush()
        return member

    async def update_role(
        self, team_id: uuid.UUID, user_id: uuid.UUID, role: str
    ) -> TeamMember | None:
        member = await self.get(team_id, user_id)
        if member is None:
            return None
        member.role = role
        await self._session.flush()
        return member

    async def remove(self, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        member = await self.get(team_id, user_id)
        if member is None:
            return False
        await self._session.delete(member)
        await self._session.flush()
        return True


__all__ = ["TeamMemberRepository", "TeamRepository"]
