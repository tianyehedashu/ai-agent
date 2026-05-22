"""定价目录可见性（成本字段遮罩）。"""

from __future__ import annotations

from domains.tenancy.domain.management_context import ManagementTeamContext
from domains.tenancy.domain.policies.team_role import TeamRole, is_team_admin_or_platform


def can_view_pricing_cost_fields(team: ManagementTeamContext) -> bool:
    return is_team_admin_or_platform(team)


def can_view_margin_dashboard(team: ManagementTeamContext) -> bool:
    """套餐毛利大盘：平台 admin，或共享团队 owner/admin；个人工作区不可见。"""
    if team.is_platform_admin:
        return True
    if team.team_kind != "shared":
        return False
    return team.team_role in (TeamRole.OWNER.value, TeamRole.ADMIN.value)


__all__ = ["can_view_margin_dashboard", "can_view_pricing_cost_fields"]
