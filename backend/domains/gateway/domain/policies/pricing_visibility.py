"""定价目录可见性（成本字段遮罩）。"""

from __future__ import annotations

from domains.tenancy.domain.management_context import ManagementTeamContext
from domains.tenancy.domain.policies.team_role import is_team_admin_or_platform


def can_view_pricing_cost_fields(team: ManagementTeamContext) -> bool:
    return is_team_admin_or_platform(team)


__all__ = ["can_view_pricing_cost_fields"]
