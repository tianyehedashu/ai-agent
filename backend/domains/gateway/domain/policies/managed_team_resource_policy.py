"""跨团队资源聚合读侧：协作团队过滤（凭据/模型共用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable
    import uuid

    from domains.gateway.domain.policies.managed_team_credentials_policy import WritableTeamSnapshot


class _TeamIncludePredicate(Protocol):
    def __call__(
        self,
        *,
        kind: str,
        role: str,
        is_platform_admin: bool,
    ) -> bool: ...


@dataclass(frozen=True)
class ManagedTeamResourceListPlan:
    tenant_ids: tuple[uuid.UUID, ...]
    queried_team_count: int
    queried_personal_team_count: int
    queried_shared_team_count: int


def _build_collaboration_team_plan(
    teams: Iterable[WritableTeamSnapshot],
    *,
    is_platform_admin: bool,
    include_team: _TeamIncludePredicate,
) -> ManagedTeamResourceListPlan:
    selected = [
        team
        for team in teams
        if team.kind != "personal"
        and include_team(
            kind=team.kind,
            role=team.role,
            is_platform_admin=is_platform_admin,
        )
    ]
    tenant_ids = tuple(team.team_id for team in selected)
    shared_count = sum(1 for team in selected if team.kind == "shared")
    return ManagedTeamResourceListPlan(
        tenant_ids=tenant_ids,
        queried_team_count=len(tenant_ids),
        queried_personal_team_count=0,
        queried_shared_team_count=shared_count,
    )


def build_managed_team_resource_list_plan(
    teams: Iterable[WritableTeamSnapshot],
    *,
    is_platform_admin: bool,
) -> ManagedTeamResourceListPlan:
    """排除 personal team，仅保留可写协作团队（写侧 / 管理操作对齐）。"""
    from domains.gateway.domain.policies.managed_team_credentials_policy import (
        is_writable_gateway_team,
    )

    return _build_collaboration_team_plan(
        teams,
        is_platform_admin=is_platform_admin,
        include_team=is_writable_gateway_team,
    )


def build_managed_team_readable_resource_list_plan(
    teams: Iterable[WritableTeamSnapshot],
    *,
    is_platform_admin: bool,
) -> ManagedTeamResourceListPlan:
    """排除 personal team，保留 membership 内全部协作团队（读侧 Tab 对齐 §6 成员可查看）。"""
    from domains.gateway.domain.policies.managed_team_credentials_policy import (
        is_readable_collaboration_gateway_team,
    )

    return _build_collaboration_team_plan(
        teams,
        is_platform_admin=is_platform_admin,
        include_team=is_readable_collaboration_gateway_team,
    )


__all__ = [
    "ManagedTeamResourceListPlan",
    "build_managed_team_readable_resource_list_plan",
    "build_managed_team_resource_list_plan",
]
