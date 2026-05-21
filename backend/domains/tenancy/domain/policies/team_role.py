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


__all__ = [
    "TeamRole",
    "assert_gateway_admin",
    "assert_team_role",
    "is_platform_admin",
    "is_team_admin_or_platform",
    "is_team_owner_or_platform",
]
