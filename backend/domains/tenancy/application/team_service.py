"""TeamService - 租户团队管理（personal / shared）。"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.ports import UserPlatformRoleLookupPort
from domains.tenancy.application.ports import GatewayTeamMembershipSnapshot, TeamSnapshot
from domains.tenancy.domain.policies.gateway_team_list_visibility import (
    is_visible_in_platform_admin_gateway_list,
)
from domains.tenancy.domain.policies.team_invite_candidate_scope import (
    SETTINGS_KEY,
    validate_invite_candidate_scope_value,
)
from domains.tenancy.domain.policies.team_list_filter import team_metadata_matches_search
from domains.tenancy.domain.policies.team_role import TeamRole, effective_team_role
from domains.tenancy.infrastructure.identity_user_role_lookup import (
    user_platform_role_lookup_for_session,
)
from domains.tenancy.infrastructure.membership_adapter import TenancyMembershipAdapter
from domains.tenancy.infrastructure.models.team import Team, TeamMember
from domains.tenancy.infrastructure.repositories.team_repository import (
    TeamMemberRepository,
    TeamRepository,
)
from libs.exceptions import (
    PersonalTeamNotInitializedError,
    TeamNotFoundError,
    TeamPermissionDeniedError,
)
from libs.iam.tenancy import MembershipPort, TenantId


class TeamService:
    """团队 / 租户作用域管理。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        membership: MembershipPort | None = None,
        user_role_lookup: UserPlatformRoleLookupPort | None = None,
    ) -> None:
        self._session = session
        self._teams = TeamRepository(session)
        self._members = TeamMemberRepository(session)
        self._membership = membership or TenancyMembershipAdapter()
        self._user_role_lookup = user_role_lookup or user_platform_role_lookup_for_session(session)

    async def _filter_platform_admin_teams(
        self,
        teams: list[Team],
        *,
        exclude_anonymous_personal: bool,
    ) -> list[Team]:
        if not exclude_anonymous_personal:
            return teams
        personal_owner_ids = list({team.owner_user_id for team in teams if team.kind == "personal"})
        roles = await self._user_role_lookup.roles_by_user_ids(personal_owner_ids)
        return [
            team
            for team in teams
            if is_visible_in_platform_admin_gateway_list(
                kind=team.kind,
                owner_user_role=roles.get(team.owner_user_id, "anonymous"),
            )
        ]

    async def ensure_personal_team(
        self,
        user_id: uuid.UUID,
        *,
        display_name: str | None = None,
    ) -> Team:
        """确保该用户有 personal team，没有则创建（幂等）。"""
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

    async def add_member(self, team_id: uuid.UUID, user_id: uuid.UUID, role: str) -> TeamMember:
        team = await self._teams.get(team_id)
        if team is None:
            raise TeamNotFoundError(str(team_id))
        if role not in ("owner", "admin", "member"):
            raise ValueError("Invalid role; expected owner, admin, or member")
        if role == "owner" and user_id != team.owner_user_id:
            raise ValueError("Only the team owner may hold the owner role")
        if team.kind == "personal" and user_id != team.owner_user_id:
            raise ValueError("Personal teams cannot have members other than the owner")
        existing = await self._members.get(team_id, user_id)
        if existing is not None:
            member = await self._members.update_role(team_id, user_id, role) or existing
        else:
            member = await self._members.add(team_id, user_id, role)
        from domains.tenancy.application.team_cache import invalidate_member

        invalidate_member(team_id, user_id)
        return member

    async def remove_member(self, team_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        team = await self._teams.get(team_id)
        if team is None:
            return False
        if team.kind == "personal" and team.owner_user_id == user_id:
            raise ValueError("Cannot remove owner from personal team")
        removed = await self._members.remove(team_id, user_id)
        if removed:
            from domains.tenancy.application.team_cache import invalidate_member

            invalidate_member(team_id, user_id)
        return removed

    async def list_user_teams(self, user_id: uuid.UUID) -> list[Team]:
        return await self._teams.list_for_user(user_id)

    async def list_teams_with_roles_for_user(
        self, user_id: uuid.UUID
    ) -> list[tuple[Team, str | None]]:
        teams = await self.list_user_teams(user_id)
        roles = await self._membership.member_roles_for_user(self._session, user_id=user_id)
        return [(team, roles.get(TenantId(team.id))) for team in teams]

    async def list_teams_for_gateway(
        self,
        user_id: uuid.UUID,
        *,
        is_platform_admin: bool,
        search: str | None = None,
        exclude_anonymous_personal: bool = True,
    ) -> list[tuple[Team, str]]:
        """Gateway 管理面团队列表：普通用户仅 membership；平台 admin 可见活跃团队。"""
        if not is_platform_admin:
            membership_items = await self.list_teams_with_roles_for_user(user_id)
            return [
                (team, role)
                for team, role in membership_items
                if role is not None
                and team_metadata_matches_search(name=team.name, slug=team.slug, search=search)
            ]

        teams = await self._teams.list_all_active()
        teams = await self._filter_platform_admin_teams(
            teams,
            exclude_anonymous_personal=exclude_anonymous_personal,
        )
        roles = await self._membership.member_roles_for_user(self._session, user_id=user_id)
        return [
            (
                team,
                effective_team_role(
                    member_role=roles.get(TenantId(team.id)),
                    is_platform_admin=True,
                ),
            )
            for team in teams
            if team_metadata_matches_search(name=team.name, slug=team.slug, search=search)
        ]

    async def get_team(self, team_id: uuid.UUID) -> Team | None:
        from bootstrap.config import settings
        from domains.tenancy.application.team_cache import (
            CACHE_MISS,
            peek_cached_team_snapshot,
            put_cached_team_snapshot,
            team_from_snapshot,
        )

        if settings.gateway_team_cache_enabled:
            cached = peek_cached_team_snapshot(team_id)
            if cached is not CACHE_MISS:
                return team_from_snapshot(cached) if cached is not None else None
        team = await self._teams.get(team_id)
        if settings.gateway_team_cache_enabled:
            put_cached_team_snapshot(team_id, team)
        return team

    async def get_personal(self, user_id: uuid.UUID) -> Team | None:
        """获取用户 personal team ORM（同域 application 编排用）。"""
        return await self._teams.get_personal(user_id)

    async def list_team_members(self, team_id: uuid.UUID) -> list[TeamMember]:
        return await self._members.list_by_team(team_id)

    async def update_team(
        self,
        team_id: uuid.UUID,
        *,
        name: str | None = None,
        settings: dict[str, Any] | None = None,
        actor_team_role: str | None = None,
    ) -> Team | None:
        merged_settings: dict[str, Any] | None = None
        if settings is not None:
            team = await self._teams.get(team_id)
            if team is None:
                return None
            if SETTINGS_KEY in settings and actor_team_role != TeamRole.OWNER.value:
                raise TeamPermissionDeniedError("Only team owner may change invite candidate scope")
            merged_settings = {**(team.settings or {}), **settings}
            if SETTINGS_KEY in settings:
                validate_invite_candidate_scope_value(settings[SETTINGS_KEY])
        updated = await self._teams.update(team_id, name=name, settings=merged_settings)
        if updated is not None:
            from domains.tenancy.application.team_cache import invalidate_team

            invalidate_team(team_id)
        return updated

    async def delete_shared_team(self, team_id: uuid.UUID) -> None:
        team = await self._teams.get(team_id)
        if team is None:
            return
        if team.kind == "personal":
            raise ValueError("Cannot delete personal team")
        await self._teams.delete(team_id)

    async def get_display_names_by_ids(self, team_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        return await self._teams.get_display_names_by_ids(team_ids)

    @staticmethod
    def _to_snapshot(team: Team) -> TeamSnapshot:
        return TeamSnapshot(
            id=team.id,
            is_active=team.is_active,
            kind=team.kind,
            owner_user_id=team.owner_user_id,
        )

    async def get_team_snapshot(self, team_id: uuid.UUID) -> TeamSnapshot | None:
        team = await self._teams.get(team_id)
        return self._to_snapshot(team) if team is not None else None

    async def get_personal_team(self, user_id: uuid.UUID) -> TeamSnapshot | None:
        """``TeamResolutionPort``：用户 personal team 快照。"""
        team = await self._teams.get_personal(user_id)
        return self._to_snapshot(team) if team is not None else None

    async def resolve_team_for_gateway_proxy(
        self,
        user_id: uuid.UUID,
        x_team_id: str | None,
    ) -> tuple[TeamSnapshot, str]:
        from domains.tenancy.domain.policies.team_target import parse_team_id_header

        team: Team | None = None
        target_id = parse_team_id_header(None, x_team_id)
        if target_id is not None:
            team = await self._teams.get(target_id)
        if team is None:
            team = await self._teams.get_personal(user_id)
        if team is None:
            raise PersonalTeamNotInitializedError()
        role = await self._membership.member_role(
            self._session,
            tenant_id=TenantId(team.id),
            user_id=user_id,
        )
        if role is None:
            raise TeamPermissionDeniedError(str(team.id))
        return self._to_snapshot(team), role

    async def list_gateway_team_memberships(
        self,
        user_id: uuid.UUID,
        *,
        is_platform_admin: bool,
        search: str | None = None,
        exclude_anonymous_personal: bool = True,
    ) -> list[GatewayTeamMembershipSnapshot]:
        """``GatewayTeamListingPort``：Gateway 管理面团队 membership 快照。"""
        teams_with_roles = await self.list_teams_for_gateway(
            user_id,
            is_platform_admin=is_platform_admin,
            search=search,
            exclude_anonymous_personal=exclude_anonymous_personal,
        )
        return [
            GatewayTeamMembershipSnapshot(team_id=team.id, kind=team.kind, role=role)
            for team, role in teams_with_roles
        ]


__all__ = ["TeamService"]
