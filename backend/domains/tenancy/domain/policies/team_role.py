"""团队角色策略（owner / admin / member + 平台 admin 旁路）。"""

from __future__ import annotations

from enum import Enum

from domains.tenancy.domain.errors import TeamPermissionDeniedError
from domains.tenancy.domain.management_context import ManagementTeamContext


class TeamRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


def is_platform_admin(team: ManagementTeamContext) -> bool:
    return team.is_platform_admin


def is_team_admin_or_platform(team: ManagementTeamContext) -> bool:
    """平台 admin 或团队 owner/admin。"""
    return team.is_platform_admin or team.team_role in (
        TeamRole.OWNER.value,
        TeamRole.ADMIN.value,
    )


def is_plain_team_member_role(*, is_platform_admin: bool, team_role: str) -> bool:
    """普通团队成员角色（非 owner/admin，且非平台 admin）；快照与 ``ManagementTeamContext`` 共用。"""
    if is_platform_admin:
        return False
    return team_role == TeamRole.MEMBER.value


def is_team_member_only(team: ManagementTeamContext) -> bool:
    """普通团队成员（非 owner/admin，且非平台 admin）。"""
    return is_plain_team_member_role(
        is_platform_admin=team.is_platform_admin,
        team_role=team.team_role,
    )


def is_team_owner_or_platform(team: ManagementTeamContext) -> bool:
    return team.is_platform_admin or team.team_role == TeamRole.OWNER.value


def assert_team_role(
    team: ManagementTeamContext,
    *roles: str,
) -> None:
    """要求当前团队角色 ∈ roles，或平台 admin。"""
    if team.is_platform_admin:
        return
    if team.team_role not in roles:
        raise TeamPermissionDeniedError(
            str(team.team_id),
            required_role=", ".join(roles),
        )


def assert_gateway_admin(team: ManagementTeamContext) -> None:
    """平台 admin 或团队 owner/admin。"""
    if is_team_admin_or_platform(team):
        return
    raise TeamPermissionDeniedError(
        str(team.team_id),
        required_role="platform admin or team admin/owner",
    )


def effective_team_role(
    *,
    member_role: str | None,
    is_platform_admin: bool,
) -> str:
    """合成管理面团队角色：平台 admin 无 membership 时视为 admin。"""
    if member_role is not None:
        return member_role
    if is_platform_admin:
        return TeamRole.ADMIN.value
    msg = "Team membership required for non-platform admin"
    raise ValueError(msg)


__all__ = [
    "TeamRole",
    "assert_gateway_admin",
    "assert_team_role",
    "effective_team_role",
    "is_plain_team_member_role",
    "is_platform_admin",
    "is_team_admin_or_platform",
    "is_team_member_only",
    "is_team_owner_or_platform",
]
