"""团队邀请候选人分页查询（User 表 + gateway_team_members 过滤）。"""

from dataclasses import dataclass
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from domains.identity.domain.policies.platform_role_policy import ANONYMOUS_ROLE
from domains.identity.infrastructure.models.user import User
from domains.tenancy.infrastructure.models.team import TeamMember

InviteCandidateScope = str


@dataclass(frozen=True, slots=True)
class InviteCandidateRow:
    id: uuid.UUID
    email: str
    name: str | None


def _base_stmt(
    *,
    team_id: uuid.UUID,
    scope: InviteCandidateScope,
    actor_user_id: uuid.UUID,
    search: str | None,
) -> Select[tuple[User]]:
    exclude_members = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
    stmt: Select[tuple[User]] = select(User).where(
        User.role != ANONYMOUS_ROLE,
        User.is_active.is_(True),
        User.id.not_in(exclude_members),
    )
    if scope == "shared_teams":
        actor_teams = select(TeamMember.team_id).where(TeamMember.user_id == actor_user_id)
        shared_users = select(TeamMember.user_id).where(TeamMember.team_id.in_(actor_teams))
        stmt = stmt.where(User.id.in_(shared_users))
    if search:
        needle = search.strip().lower()
        if needle:
            pattern = f"%{needle}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.email).like(pattern),
                    func.lower(func.coalesce(User.name, "")).like(pattern),
                )
            )
    return stmt


class UserInviteCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self,
        *,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        scope: InviteCandidateScope,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[InviteCandidateRow]:
        stmt = _base_stmt(
            team_id=team_id,
            scope=scope,
            actor_user_id=actor_user_id,
            search=search,
        )
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [
            InviteCandidateRow(id=u.id, email=u.email, name=u.name) for u in result.scalars().all()
        ]

    async def count(
        self,
        *,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        scope: InviteCandidateScope,
        search: str | None,
    ) -> int:
        stmt = _base_stmt(
            team_id=team_id,
            scope=scope,
            actor_user_id=actor_user_id,
            search=search,
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self._session.execute(count_stmt)
        return result.scalar() or 0


__all__ = ["InviteCandidateRow", "UserInviteCandidateRepository"]
