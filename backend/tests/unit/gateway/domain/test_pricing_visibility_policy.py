"""pricing_visibility 策略单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.policies.pricing_visibility import can_view_pricing_cost_fields
from domains.tenancy.domain.management_context import ManagementTeamContext


def test_platform_admin_can_view_cost() -> None:
    ctx = ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="standard",
        team_role="member",
        user_id=uuid.uuid4(),
        is_platform_admin=True,
    )
    assert can_view_pricing_cost_fields(ctx) is True


def test_member_cannot_view_cost() -> None:
    ctx = ManagementTeamContext(
        team_id=uuid.uuid4(),
        team_kind="standard",
        team_role="member",
        user_id=uuid.uuid4(),
        is_platform_admin=False,
    )
    assert can_view_pricing_cost_fields(ctx) is False
