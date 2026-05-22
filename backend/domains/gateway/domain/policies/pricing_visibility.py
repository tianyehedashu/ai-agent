"""定价目录可见性（成本字段遮罩）。"""

from __future__ import annotations

from domains.tenancy.domain.management_context import ManagementTeamContext
from domains.tenancy.domain.policies.team_role import is_team_admin_or_platform


def can_view_pricing_cost_fields(team: ManagementTeamContext) -> bool:
    return is_team_admin_or_platform(team)


def can_view_margin_dashboard(team: ManagementTeamContext) -> bool:
    """套餐毛利大盘:**仅平台管理员**可见。

    设计动机:套餐毛利涉及上游成本与下游售价的差额(平台经营数据),
    任何团队/工作区角色(含共享团队 owner/admin)均不应看到。
    """
    return team.is_platform_admin


__all__ = ["can_view_margin_dashboard", "can_view_pricing_cost_fields"]
