"""跨团队可管理模型用量聚合单测。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.gateway.application.management.managed_team_model_usage_reads import (
    aggregate_managed_team_models_route_usage,
)


@pytest.mark.asyncio
async def test_aggregate_managed_team_models_route_usage_adds_team_id() -> None:
    session = AsyncMock()
    team_a = uuid.uuid4()
    team_b = uuid.uuid4()
    user_id = uuid.uuid4()

    membership_a = SimpleNamespace(team_id=team_a, role="owner", kind="shared")
    membership_b = SimpleNamespace(team_id=team_b, role="admin", kind="shared")

    row_a = {
        "route_name": "model-a",
        "workspace": {"requests": 2},
        "user": {"requests": 1},
    }
    row_b = {
        "route_name": "model-b",
        "workspace": {"requests": 1},
        "user": {"requests": 0},
    }

    async def _aggregate(_ctx, *, days, provider, route_names, page, page_size):
        _ = days, provider, route_names, page, page_size
        if _ctx.team_id == team_a:
            return [row_a], 1, SimpleNamespace(), SimpleNamespace()
        return [row_b], 1, SimpleNamespace(), SimpleNamespace()

    with patch(
        "domains.gateway.application.management.managed_team_model_usage_reads.TeamService"
    ) as team_svc_cls, patch(
        "domains.gateway.application.management.managed_team_model_usage_reads.GatewayManagementReadService"
    ) as reads_cls:
        team_svc_cls.return_value.list_gateway_team_memberships = AsyncMock(
            return_value=[membership_a, membership_b]
        )
        reads_cls.return_value.aggregate_gateway_model_route_usage = AsyncMock(
            side_effect=_aggregate
        )

        items, total, _start, _end = await aggregate_managed_team_models_route_usage(
            session,
            user_id=user_id,
            is_platform_admin=False,
            days=7,
            page=1,
            page_size=10,
        )

    assert total == 2
    assert {i["route_name"] for i in items} == {"model-a", "model-b"}
    team_ids = {i["team_id"] for i in items}
    assert team_ids == {team_a, team_b}


@pytest.mark.asyncio
async def test_aggregate_managed_team_models_route_usage_route_names_filter() -> None:
    session = AsyncMock()
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    membership = SimpleNamespace(team_id=team_id, role="owner", kind="shared")
    row = {
        "route_name": "keep-me",
        "workspace": {"requests": 1},
        "user": {"requests": 0},
    }

    with patch(
        "domains.gateway.application.management.managed_team_model_usage_reads.TeamService"
    ) as team_svc_cls, patch(
        "domains.gateway.application.management.managed_team_model_usage_reads.GatewayManagementReadService"
    ) as reads_cls:
        team_svc_cls.return_value.list_gateway_team_memberships = AsyncMock(
            return_value=[membership]
        )
        reads_cls.return_value.aggregate_gateway_model_route_usage = AsyncMock(
            return_value=([row], 1, SimpleNamespace(), SimpleNamespace())
        )

        items, total, _start, _end = await aggregate_managed_team_models_route_usage(
            session,
            user_id=user_id,
            is_platform_admin=False,
            days=7,
            route_names=["keep-me"],
            page=1,
            page_size=20,
        )

    assert total == 1
    assert len(items) == 1
    assert items[0]["route_name"] == "keep-me"
    assert items[0]["team_id"] == team_id


@pytest.mark.asyncio
async def test_aggregate_managed_team_models_route_usage_excludes_unreadable_teams() -> None:
    session = AsyncMock()
    user_id = uuid.uuid4()
    readable_team = uuid.uuid4()
    unreadable_team = uuid.uuid4()
    memberships = [
        SimpleNamespace(team_id=readable_team, role="member", kind="shared"),
        SimpleNamespace(team_id=unreadable_team, role="viewer", kind="shared"),
    ]

    aggregate_mock = AsyncMock(
        return_value=([], 0, SimpleNamespace(), SimpleNamespace())
    )

    with patch(
        "domains.gateway.application.management.managed_team_model_usage_reads.TeamService"
    ) as team_svc_cls, patch(
        "domains.gateway.application.management.managed_team_model_usage_reads.GatewayManagementReadService"
    ) as reads_cls:
        team_svc_cls.return_value.list_gateway_team_memberships = AsyncMock(
            return_value=memberships
        )
        reads_cls.return_value.aggregate_gateway_model_route_usage = aggregate_mock

        await aggregate_managed_team_models_route_usage(
            session,
            user_id=user_id,
            is_platform_admin=False,
            days=7,
        )

    queried_team_ids = {call.args[0].team_id for call in aggregate_mock.await_args_list}
    assert queried_team_ids == {readable_team}


@pytest.mark.asyncio
async def test_aggregate_managed_team_models_route_usage_no_shared_teams() -> None:
    session = AsyncMock()
    user_id = uuid.uuid4()
    personal = SimpleNamespace(team_id=uuid.uuid4(), role="owner", kind="personal")

    with patch(
        "domains.gateway.application.management.managed_team_model_usage_reads.TeamService"
    ) as team_svc_cls:
        team_svc_cls.return_value.list_gateway_team_memberships = AsyncMock(
            return_value=[personal]
        )

        items, total, start, end = await aggregate_managed_team_models_route_usage(
            session,
            user_id=user_id,
            is_platform_admin=False,
            days=7,
        )

    assert items == []
    assert total == 0
    assert start is not None
    assert end is not None
