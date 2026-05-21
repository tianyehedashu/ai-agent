"""Tenancy 域策略。"""

from domains.tenancy.domain.policies.team_role import (
    TeamRole,
    assert_gateway_admin,
    assert_team_role,
    is_platform_admin,
    is_team_admin_or_platform,
    is_team_owner_or_platform,
)

__all__ = [
    "TeamRole",
    "assert_gateway_admin",
    "assert_team_role",
    "is_platform_admin",
    "is_team_admin_or_platform",
    "is_team_owner_or_platform",
]
