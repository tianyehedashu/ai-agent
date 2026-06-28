"""Gateway 请求日志 member 可见性策略（纯函数）。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.visibility.usage_log_visibility import (
    UsageLogAccessSnapshot,
    member_can_view_request_log_record,
    member_requires_request_log_detail_filter,
    platform_aggregation_allowed,
    snapshot_is_team_member_only,
    workspace_axis_member_user_id,
)
from domains.gateway.domain.vkey.virtual_key_access import actor_owns_non_system_vkey


@pytest.mark.unit
def test_platform_aggregation_allowed() -> None:
    admin_snap = UsageLogAccessSnapshot(
        is_platform_admin=True,
        team_role="member",
        user_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
    )
    assert platform_aggregation_allowed(admin_snap) is True

    owner_snap = UsageLogAccessSnapshot(
        is_platform_admin=False,
        team_role="owner",
        user_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
    )
    assert platform_aggregation_allowed(owner_snap) is False


@pytest.mark.unit
def test_workspace_axis_member_user_id_for_team_member() -> None:
    uid = uuid.uuid4()
    snap = UsageLogAccessSnapshot(
        is_platform_admin=False,
        team_role="member",
        user_id=uid,
        team_id=uuid.uuid4(),
    )
    assert workspace_axis_member_user_id(snap, vkey_id=None) == uid
    assert workspace_axis_member_user_id(snap, vkey_id=uuid.uuid4()) == uid


@pytest.mark.unit
def test_workspace_axis_skips_filter_for_admin() -> None:
    snap = UsageLogAccessSnapshot(
        is_platform_admin=True,
        team_role="member",
        user_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
    )
    assert workspace_axis_member_user_id(snap, vkey_id=None) is None


@pytest.mark.unit
def test_member_can_view_own_platform_inbound_log() -> None:
    uid = uuid.uuid4()
    snap = UsageLogAccessSnapshot(
        is_platform_admin=False,
        team_role="member",
        user_id=uid,
        team_id=uuid.uuid4(),
    )
    assert member_requires_request_log_detail_filter(snap) is True
    assert member_can_view_request_log_record(
        snap,
        record_user_id=uid,
        record_has_vkey=False,
        vkey_owned_by_user=False,
    )
    assert not member_can_view_request_log_record(
        snap,
        record_user_id=uuid.uuid4(),
        record_has_vkey=False,
        vkey_owned_by_user=False,
    )


@pytest.mark.unit
def test_member_can_view_owned_vkey_log() -> None:
    snap = UsageLogAccessSnapshot(
        is_platform_admin=False,
        team_role="member",
        user_id=uuid.uuid4(),
        team_id=uuid.uuid4(),
    )
    assert member_can_view_request_log_record(
        snap,
        record_user_id=None,
        record_has_vkey=True,
        vkey_owned_by_user=True,
    )
    assert not member_can_view_request_log_record(
        snap,
        record_user_id=None,
        record_has_vkey=True,
        vkey_owned_by_user=False,
    )


@pytest.mark.unit
def test_snapshot_is_team_member_only() -> None:
    uid = uuid.uuid4()
    member_snap = UsageLogAccessSnapshot(
        is_platform_admin=False,
        team_role="member",
        user_id=uid,
        team_id=uuid.uuid4(),
    )
    assert snapshot_is_team_member_only(member_snap)
    assert workspace_axis_member_user_id(member_snap) == uid

    admin_snap = UsageLogAccessSnapshot(
        is_platform_admin=False,
        team_role="admin",
        user_id=uid,
        team_id=uuid.uuid4(),
    )
    assert not snapshot_is_team_member_only(admin_snap)
    assert workspace_axis_member_user_id(admin_snap) is None


@pytest.mark.unit
def test_actor_owns_non_system_vkey_matches_virtual_key_access() -> None:
    owner = uuid.uuid4()
    assert actor_owns_non_system_vkey(
        created_by_user_id=owner,
        actor_user_id=owner,
        is_system=False,
    )
    assert not actor_owns_non_system_vkey(
        created_by_user_id=owner,
        actor_user_id=uuid.uuid4(),
        is_system=False,
    )
    assert not actor_owns_non_system_vkey(
        created_by_user_id=owner,
        actor_user_id=owner,
        is_system=True,
    )
