"""跨团队可管理资源聚合读侧：可写协作团队过滤（凭据/模型共用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    import uuid

    from domains.gateway.domain.policies.managed_team_credentials_policy import WritableTeamSnapshot


@dataclass(frozen=True)
class ManagedTeamResourceListPlan:
    tenant_ids: tuple[uuid.UUID, ...]
    queried_team_count: int
    queried_personal_team_count: int
    queried_shared_team_count: int


def build_managed_team_resource_list_plan(
    teams: Iterable[WritableTeamSnapshot],
    *,
    is_platform_admin: bool,
) -> ManagedTeamResourceListPlan:
    """排除 personal team，仅保留可写协作团队（与前端协作团队 Tab 对齐）。"""
    from domains.gateway.domain.policies.managed_team_credentials_policy import (
        WritableTeamSnapshot,
        is_writable_gateway_team,
    )

    writable = [
        team
        for team in teams
        if team.kind != "personal"
        and is_writable_gateway_team(
            kind=team.kind,
            role=team.role,
            is_platform_admin=is_platform_admin,
        )
    ]
    tenant_ids = tuple(team.team_id for team in writable)
    personal_count = 0
    shared_count = sum(1 for team in writable if team.kind == "shared")
    return ManagedTeamResourceListPlan(
        tenant_ids=tenant_ids,
        queried_team_count=len(tenant_ids),
        queried_personal_team_count=personal_count,
        queried_shared_team_count=shared_count,
    )


__all__ = [
    "ManagedTeamResourceListPlan",
    "build_managed_team_resource_list_plan",
]
