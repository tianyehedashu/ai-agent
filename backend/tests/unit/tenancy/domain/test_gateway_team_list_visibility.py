"""gateway_team_list_visibility 单元测试。"""

from __future__ import annotations

from domains.tenancy.domain.policies.gateway_team_list_visibility import (
    is_visible_in_platform_admin_gateway_list,
)


def test_shared_team_always_visible() -> None:
    assert is_visible_in_platform_admin_gateway_list(
        kind="shared",
        owner_user_role="anonymous",
    )


def test_personal_team_visible_for_registered_user() -> None:
    assert is_visible_in_platform_admin_gateway_list(
        kind="personal",
        owner_user_role="user",
    )


def test_personal_team_hidden_for_anonymous_owner() -> None:
    assert not is_visible_in_platform_admin_gateway_list(
        kind="personal",
        owner_user_role="anonymous",
    )
