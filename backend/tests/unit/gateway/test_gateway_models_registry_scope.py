"""GET /teams/{id}/models?registry_scope= 语义与权限。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
from domains.gateway.application.management import GatewayManagementReadService
from domains.gateway.domain.policies.model_selection import registry_kind_for_merged_row
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService


@pytest.mark.asyncio
async def test_list_gateway_models_registry_scope_team_excludes_system(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    reads = GatewayManagementReadService(db_session)

    callable_rows = await reads.list_gateway_models(
        team.id, registry_scope="callable", only_enabled=True
    )
    team_rows = await reads.list_gateway_models(
        team.id, registry_scope="team", only_enabled=False
    )
    if not callable_rows:
        pytest.skip("catalog sync produced no system models")

    system_names = {r.name for r in callable_rows if registry_kind_for_merged_row(r) == "system"}
    team_names = {r.name for r in team_rows}
    assert system_names.isdisjoint(team_names)


@pytest.mark.asyncio
async def test_list_gateway_models_registry_scope_system(db_session) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    reads = GatewayManagementReadService(db_session)
    system_rows = await reads.list_gateway_models(
        uuid.uuid4(), registry_scope="system", only_enabled=True
    )
    if not system_rows:
        pytest.skip("catalog sync produced no system models")
    assert all(registry_kind_for_merged_row(r) == "system" for r in system_rows)


@pytest.mark.asyncio
async def test_list_gateway_models_registry_scope_requestable_excludes_failed(
    db_session, test_user
) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    reads = GatewayManagementReadService(db_session)
    repo = GatewayModelRepository(db_session)
    system_rows = await repo.list_system(only_enabled=True)
    if not system_rows:
        pytest.skip("catalog sync produced no system models")
    target = system_rows[0]
    await repo.update_system(
        target.id,
        last_test_status="failed",
        last_test_reason="unit: forced failed",
    )
    await db_session.flush()

    requestable = await reads.list_gateway_models(
        team.id, registry_scope="requestable", only_enabled=True
    )
    assert target.name not in {r.name for r in requestable}
    assert target.name in {
        r.name
        for r in await reads.list_gateway_models(
            team.id, registry_scope="callable", only_enabled=True
        )
    }

