"""GatewayManagementReadService 请求日志列表/详情（成员 + 平台 sk 入站）单测。

Stage 2 起：仓储层使用 ``UsageAxis`` 值对象，本测试断言 ``_resolve_usage_axis`` 选择正确,
``member_user_id`` 等价路径仍然生效。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.domain.errors import TeamPermissionDeniedError
from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.domain.usage_read_model import UsageAggregation
from domains.tenancy.domain.management_context import ManagementTeamContext


@pytest.mark.asyncio
async def test_list_request_logs_member_workspace_keeps_own_vkey_and_own_platform_sk() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    member_id = uuid.uuid4()
    other_user = uuid.uuid4()
    my_vkey_id = uuid.uuid4()

    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=member_id,
        is_platform_admin=False,
    )

    log_own_vkey = SimpleNamespace(vkey_id=my_vkey_id, user_id=other_user)
    log_platform_own = SimpleNamespace(vkey_id=None, user_id=member_id)

    async def _list_by_axis(axis: UsageAxis, *_args: Any, **_kwargs: Any) -> tuple[list[Any], int]:
        assert axis.is_workspace()
        assert axis.team_id == team_id
        assert axis.member_user_id == member_id
        return [log_own_vkey, log_platform_own], 2

    svc._logs.list_by_axis = AsyncMock(side_effect=_list_by_axis)
    svc._vkeys.list_for_tenant = AsyncMock(side_effect=AssertionError("member list must not list vkeys"))

    items, total = await svc.list_request_logs(
        ctx,
        usage_aggregation=UsageAggregation.WORKSPACE,
        page=1,
        page_size=20,
        start=None,
        end=None,
        status_filter=None,
        capability=None,
        vkey_id=None,
        credential_id=None,
    )
    assert total == 2
    assert len(items) == 2
    assert log_own_vkey in items
    assert log_platform_own in items


@pytest.mark.asyncio
async def test_list_request_logs_admin_no_extra_filter() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    uid = uuid.uuid4()
    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=uid,
        is_platform_admin=True,
    )
    rows: list[Any] = [SimpleNamespace(vkey_id=None, user_id=uuid.uuid4())]

    async def _list_by_axis(axis: UsageAxis, *_args: Any, **_kwargs: Any) -> tuple[list[Any], int]:
        assert axis.is_workspace()
        assert axis.team_id == team_id
        assert axis.member_user_id is None
        return rows, 1

    svc._logs.list_by_axis = AsyncMock(side_effect=_list_by_axis)
    svc._vkeys.list_for_tenant = AsyncMock(side_effect=AssertionError("admin path must not list vkeys"))

    items, total = await svc.list_request_logs(
        ctx,
        usage_aggregation=UsageAggregation.WORKSPACE,
        page=1,
        page_size=20,
        start=None,
        end=None,
        status_filter=None,
        capability=None,
        vkey_id=None,
    )
    assert items == rows
    assert total == 1


@pytest.mark.asyncio
async def test_list_request_logs_user_aggregation_uses_user_axis() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    uid = uuid.uuid4()
    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=uid,
        is_platform_admin=False,
    )

    captured: dict[str, Any] = {}

    async def _list_by_axis(axis: UsageAxis, *_args: Any, **_kwargs: Any) -> tuple[list[Any], int]:
        captured["axis"] = axis
        return [], 0

    svc._logs.list_by_axis = AsyncMock(side_effect=_list_by_axis)

    await svc.list_request_logs(
        ctx,
        usage_aggregation=UsageAggregation.USER,
        page=1,
        page_size=20,
        start=None,
        end=None,
        status_filter=None,
        capability=None,
        vkey_id=None,
    )
    axis: UsageAxis = captured["axis"]
    assert axis.is_user()
    assert axis.user_id == uid


@pytest.mark.asyncio
async def test_get_request_log_member_allows_own_vkey_or_own_platform_sk() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    member_id = uuid.uuid4()
    my_vkey_id = uuid.uuid4()
    log_id = uuid.uuid4()

    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=member_id,
        is_platform_admin=False,
    )
    own_vkey = SimpleNamespace(
        tenant_id=team_id,
        created_by_user_id=member_id,
        is_system=False,
    )
    svc._vkeys.get = AsyncMock(return_value=own_vkey)

    rec_vkey = SimpleNamespace(vkey_id=my_vkey_id, user_id=uuid.uuid4())
    svc._logs.get_by_axis = AsyncMock(return_value=rec_vkey)
    out = await svc.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)
    assert out is rec_vkey

    rec_platform = SimpleNamespace(vkey_id=None, user_id=member_id)
    svc._logs.get_by_axis = AsyncMock(return_value=rec_platform)
    out2 = await svc.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)
    assert out2 is rec_platform


@pytest.mark.asyncio
async def test_get_request_log_member_denies_other_vkey_and_other_platform_sk() -> None:
    session = MagicMock()
    svc = GatewayManagementReadService(session)
    team_id = uuid.uuid4()
    member_id = uuid.uuid4()
    other_vkey_id = uuid.uuid4()
    log_id = uuid.uuid4()

    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=member_id,
        is_platform_admin=False,
    )
    other_vkey = SimpleNamespace(
        tenant_id=team_id,
        created_by_user_id=uuid.uuid4(),
        is_system=False,
    )
    svc._vkeys.get = AsyncMock(return_value=other_vkey)

    rec_other_vkey = SimpleNamespace(vkey_id=other_vkey_id, user_id=member_id)
    svc._logs.get_by_axis = AsyncMock(return_value=rec_other_vkey)
    with pytest.raises(TeamPermissionDeniedError):
        await svc.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)

    rec_platform_other = SimpleNamespace(vkey_id=None, user_id=uuid.uuid4())
    svc._logs.get_by_axis = AsyncMock(return_value=rec_platform_other)
    with pytest.raises(TeamPermissionDeniedError):
        await svc.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)


def test_resolve_usage_axis_member_keeps_filter_when_vkey_filter_set() -> None:
    """成员 workspace 轴在指定 ``vkey_id`` 时仍附加 member_user_id（防列表越权）。"""
    team_id = uuid.uuid4()
    uid = uuid.uuid4()
    ctx_member = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=uid,
        is_platform_admin=False,
    )

    axis = GatewayManagementReadService._resolve_usage_axis(
        ctx_member, UsageAggregation.WORKSPACE
    )
    assert axis.is_workspace() and axis.member_user_id == uid

    axis2 = GatewayManagementReadService._resolve_usage_axis(
        ctx_member, UsageAggregation.WORKSPACE, vkey_id=uuid.uuid4()
    )
    assert axis2.is_workspace() and axis2.member_user_id == uid

    axis3 = GatewayManagementReadService._resolve_usage_axis(
        ctx_member, UsageAggregation.USER
    )
    assert axis3.is_user() and axis3.user_id == uid

    ctx_admin = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=uid,
        is_platform_admin=True,
    )
    axis4 = GatewayManagementReadService._resolve_usage_axis(
        ctx_admin, UsageAggregation.WORKSPACE
    )
    assert axis4.is_workspace() and axis4.member_user_id is None
