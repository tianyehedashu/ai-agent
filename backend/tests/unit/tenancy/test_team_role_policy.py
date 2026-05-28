"""Tenancy team_role 策略单测。"""

import pytest

from domains.tenancy.domain.policies.team_role import TeamRole, effective_team_role


def test_effective_team_role_returns_member_role_when_present() -> None:
    assert (
        effective_team_role(member_role=TeamRole.OWNER.value, is_platform_admin=False)
        == TeamRole.OWNER.value
    )


def test_effective_team_role_platform_admin_without_membership() -> None:
    assert effective_team_role(member_role=None, is_platform_admin=True) == TeamRole.ADMIN.value


def test_effective_team_role_non_admin_without_membership_raises() -> None:
    with pytest.raises(ValueError, match="membership required"):
        effective_team_role(member_role=None, is_platform_admin=False)
