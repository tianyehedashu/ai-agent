"""Gateway 请求日志 member 可见性策略（纯函数）。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.policies.usage_log_visibility import (
    UsageLogAccessSnapshot,
    member_can_view_request_log_record,
    member_requires_request_log_detail_filter,
    workspace_axis_member_user_id,
)


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
    assert workspace_axis_member_user_id(snap, vkey_id=uuid.uuid4()) is None


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
