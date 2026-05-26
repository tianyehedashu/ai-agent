"""managed_team_credentials_policy 单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.policies.managed_team_credentials_policy import (
    WritableTeamSnapshot,
    build_managed_team_credential_list_plan,
    is_writable_gateway_team,
)
from domains.tenancy.domain.policies.team_role import TeamRole


def _snap(kind: str, role: str) -> WritableTeamSnapshot:
    return WritableTeamSnapshot(team_id=uuid.uuid4(), kind=kind, role=role)


def test_is_writable_gateway_team_platform_admin() -> None:
    assert is_writable_gateway_team(
        kind="shared",
        role=TeamRole.MEMBER.value,
        is_platform_admin=True,
    )


def test_is_writable_gateway_team_personal() -> None:
    assert is_writable_gateway_team(
        kind="personal",
        role=TeamRole.OWNER.value,
        is_platform_admin=False,
    )


def test_is_writable_gateway_team_shared_admin() -> None:
    assert is_writable_gateway_team(
        kind="shared",
        role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )


def test_is_writable_gateway_team_shared_member_denied() -> None:
    assert not is_writable_gateway_team(
        kind="shared",
        role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )


def test_build_managed_team_credential_list_plan_filters_members() -> None:
    personal = _snap("personal", TeamRole.OWNER.value)
    shared_admin = _snap("shared", TeamRole.ADMIN.value)
    shared_member = _snap("shared", TeamRole.MEMBER.value)

    plan = build_managed_team_credential_list_plan(
        [personal, shared_admin, shared_member],
        is_platform_admin=False,
    )

    assert plan.queried_team_count == 2
    assert plan.queried_personal_team_count == 1
    assert plan.queried_shared_team_count == 1
    assert personal.team_id in plan.tenant_ids
    assert shared_admin.team_id in plan.tenant_ids
    assert shared_member.team_id not in plan.tenant_ids


def test_build_managed_team_credential_list_plan_platform_admin_includes_all() -> None:
    teams = [_snap("shared", TeamRole.MEMBER.value), _snap("shared", TeamRole.ADMIN.value)]
    plan = build_managed_team_credential_list_plan(teams, is_platform_admin=True)
    assert plan.queried_team_count == 2
    assert plan.queried_personal_team_count == 0
    assert plan.queried_shared_team_count == 2
