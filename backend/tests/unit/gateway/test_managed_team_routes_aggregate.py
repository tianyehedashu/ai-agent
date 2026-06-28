"""managed_team_route_reads 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.route.management.managed_team_route_reads import (
    list_managed_team_routes_for_actor,
)
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from libs.api.pagination import PageParams


@dataclass(frozen=True)
class _Membership:
    team_id: uuid.UUID
    kind: str
    role: str


def _team_route(route_id: uuid.UUID, tenant_id: uuid.UUID, virtual_model: str) -> GatewayRoute:
    row = MagicMock(spec=GatewayRoute)
    row.id = route_id
    row.tenant_id = tenant_id
    row.virtual_model = virtual_model
    return row


@pytest.mark.asyncio
async def test_list_managed_team_routes_includes_personal_and_paginates() -> None:
    user_id = uuid.uuid4()
    personal_id = uuid.uuid4()
    shared_id = uuid.uuid4()
    personal_route_id = uuid.uuid4()

    session = MagicMock()
    team_listing = MagicMock()
    team_listing.list_gateway_team_memberships = AsyncMock(
        return_value=[
            _Membership(team_id=personal_id, kind="personal", role="owner"),
            _Membership(team_id=shared_id, kind="shared", role="admin"),
        ]
    )

    personal_route = _team_route(personal_route_id, personal_id, "my-route")

    route_repo = MagicMock()
    route_repo.list_merged_routes_for_tenants = AsyncMock(return_value=[personal_route])

    with patch(
        "domains.gateway.application.route.management.managed_team_route_reads.GatewayRouteRepository",
        return_value=route_repo,
    ):
        result = await list_managed_team_routes_for_actor(
            session,
            user_id=user_id,
            is_platform_admin=False,
            page_params=PageParams(page=1, page_size=20),
            team_listing=team_listing,
        )

    assert result.queried_team_count == 2
    assert result.queried_personal_team_count == 1
    assert result.queried_shared_team_count == 1
    assert result.total == 1
    assert [row.id for row in result.page_items] == [personal_route_id]
    assert result.tenant_ids_with_routes == (personal_id,)
    assert result.tenant_kind_by_id == {
        personal_id: "personal",
        shared_id: "shared",
    }
    route_repo.list_merged_routes_for_tenants.assert_awaited_once_with(
        [personal_id, shared_id],
        only_enabled=False,
    )
