"""pricing_visibility 策略单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.policies.pricing_visibility import (
    can_view_margin_dashboard,
    can_view_pricing_cost_fields,
)
from domains.tenancy.domain.management_context import ManagementTeamContext


def _ctx(
    *,
    team_kind: str,
    team_role: str,
    is_platform_admin: bool,
) -> ManagementTeamContext:
    return ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind=team_kind,
        team_role=team_role,
        user_id=uuid.uuid4(),
        is_platform_admin=is_platform_admin,
    )


def test_platform_admin_can_view_cost() -> None:
    ctx = _ctx(team_kind="standard", team_role="member", is_platform_admin=True)
    assert can_view_pricing_cost_fields(ctx) is True


def test_member_cannot_view_cost() -> None:
    ctx = _ctx(team_kind="standard", team_role="member", is_platform_admin=False)
    assert can_view_pricing_cost_fields(ctx) is False


def test_platform_admin_can_view_margin_dashboard() -> None:
    """平台管理员可见——这是套餐毛利大盘的**唯一**可见角色。"""
    ctx = _ctx(team_kind="standard", team_role="member", is_platform_admin=True)
    assert can_view_margin_dashboard(ctx) is True


def test_personal_owner_cannot_view_margin_dashboard() -> None:
    ctx = _ctx(team_kind="personal", team_role="owner", is_platform_admin=False)
    assert can_view_margin_dashboard(ctx) is False


def test_shared_owner_cannot_view_margin_dashboard() -> None:
    """共享团队 owner 不再可见（套餐毛利属平台经营数据）。"""
    ctx = _ctx(team_kind="shared", team_role="owner", is_platform_admin=False)
    assert can_view_margin_dashboard(ctx) is False


def test_shared_admin_cannot_view_margin_dashboard() -> None:
    ctx = _ctx(team_kind="shared", team_role="admin", is_platform_admin=False)
    assert can_view_margin_dashboard(ctx) is False


def test_shared_member_cannot_view_margin_dashboard() -> None:
    ctx = _ctx(team_kind="shared", team_role="member", is_platform_admin=False)
    assert can_view_margin_dashboard(ctx) is False
