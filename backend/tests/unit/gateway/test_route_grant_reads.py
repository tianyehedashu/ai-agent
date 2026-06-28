"""``list_shared_routes_for_team`` — 共享路由列表投影。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from domains.gateway.application.route.management.route_grant_reads import list_shared_routes_for_team
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from domains.gateway.infrastructure.models.gateway_route_team_grant import GatewayRouteTeamGrant


@pytest.mark.asyncio
async def test_list_shared_routes_includes_primary_models(db_session, test_user) -> None:
    from domains.tenancy.application.team_service import TeamService

    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    consumer = await teams.create_team(
        name=f"consumer-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
    )
    route = GatewayRoute(
        tenant_id=personal.id,
        virtual_model="owner-route",
        primary_models=["model-a", "model-b"],
        enabled=True,
        created_by_user_id=test_user.id,
    )
    db_session.add(route)
    await db_session.flush()
    grant = GatewayRouteTeamGrant(
        route_id=route.id,
        tenant_id=consumer.id,
        exposed_alias="shared-alias",
        granted_by_user_id=test_user.id,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(grant)
    await db_session.commit()

    rows = await list_shared_routes_for_team(db_session, consumer.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.exposed_alias == "shared-alias"
    assert row.virtual_model == "owner-route"
    assert row.primary_models == ["model-a", "model-b"]
    assert row.enabled is True
