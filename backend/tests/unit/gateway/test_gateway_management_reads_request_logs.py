"""GatewayManagementReadService 请求日志列表/详情（成员 + 平台 sk 入站）单测。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.reads import GatewayManagementReadService
from domains.gateway.domain.errors import TeamPermissionDeniedError
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
    other_vkey_id = uuid.uuid4()

    ctx = ManagementTeamContext(
        team_id=team_id,
        team_kind="shared",
        team_role="member",
        user_id=member_id,
        is_platform_admin=False,
    )

    log_own_vkey = SimpleNamespace(vkey_id=my_vkey_id, user_id=other_user)
    log_other_vkey = SimpleNamespace(vkey_id=other_vkey_id, user_id=member_id)
    log_platform_own = SimpleNamespace(vkey_id=None, user_id=member_id)
    log_platform_other = SimpleNamespace(vkey_id=None, user_id=other_user)

    svc._logs.list_for_team = AsyncMock(
        return_value=(
            [log_own_vkey, log_other_vkey, log_platform_own, log_platform_other],
            4,
        )
    )
    my_key = SimpleNamespace(id=my_vkey_id, created_by_user_id=member_id, is_system=False)
    svc._vkeys.list_by_team = AsyncMock(return_value=[my_key])

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
    assert total == 4
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
    svc._logs.list_for_team = AsyncMock(return_value=(rows, 1))
    svc._vkeys.list_by_team = AsyncMock(side_effect=AssertionError("admin path must not list vkeys"))

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
    my_key = SimpleNamespace(id=my_vkey_id, created_by_user_id=member_id, is_system=False)
    svc._vkeys.list_by_team = AsyncMock(return_value=[my_key])

    rec_vkey = SimpleNamespace(vkey_id=my_vkey_id, user_id=uuid.uuid4())
    svc._logs.get_for_team = AsyncMock(return_value=rec_vkey)
    out = await svc.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)
    assert out is rec_vkey

    rec_platform = SimpleNamespace(vkey_id=None, user_id=member_id)
    svc._logs.get_for_team = AsyncMock(return_value=rec_platform)
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
    my_key = SimpleNamespace(id=uuid.uuid4(), created_by_user_id=member_id, is_system=False)
    svc._vkeys.list_by_team = AsyncMock(return_value=[my_key])

    rec_other_vkey = SimpleNamespace(vkey_id=other_vkey_id, user_id=member_id)
    svc._logs.get_for_team = AsyncMock(return_value=rec_other_vkey)
    with pytest.raises(TeamPermissionDeniedError):
        await svc.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)

    rec_platform_other = SimpleNamespace(vkey_id=None, user_id=uuid.uuid4())
    svc._logs.get_for_team = AsyncMock(return_value=rec_platform_other)
    with pytest.raises(TeamPermissionDeniedError):
        await svc.get_request_log(ctx, log_id, usage_aggregation=UsageAggregation.WORKSPACE)
