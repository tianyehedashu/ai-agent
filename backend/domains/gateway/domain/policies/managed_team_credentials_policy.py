"""跨团队可管理凭据聚合读侧：可写团队过滤（对齐 Gateway 管理面 RBAC）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from domains.tenancy.domain.policies.team_role import TeamRole

from domains.gateway.domain.policies.managed_team_resource_policy import (
    ManagedTeamResourceListPlan as ManagedTeamCredentialListPlan,
    build_managed_team_resource_list_plan as build_managed_team_credential_list_plan,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    import uuid


@dataclass(frozen=True)
class WritableTeamSnapshot:
    team_id: uuid.UUID
    kind: str
    role: str


def is_writable_gateway_team(
    *,
    kind: str,
    role: str,
    is_platform_admin: bool,
) -> bool:
    """与前端 ``filterGatewayWritableTeams`` / ``is_team_admin_or_platform`` 对齐。"""
    if is_platform_admin:
        return True
    if kind == "personal":
        return True
    return role in (TeamRole.OWNER.value, TeamRole.ADMIN.value)


def filter_writable_team_ids(
    teams: Iterable[WritableTeamSnapshot],
    *,
    is_platform_admin: bool,
) -> list[uuid.UUID]:
    return [
        team.team_id
        for team in teams
        if is_writable_gateway_team(
            kind=team.kind,
            role=team.role,
            is_platform_admin=is_platform_admin,
        )
    ]


__all__ = [
    "ManagedTeamCredentialListPlan",
    "WritableTeamSnapshot",
    "build_managed_team_credential_list_plan",
    "filter_writable_team_ids",
    "is_writable_gateway_team",
]
