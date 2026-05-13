"""GatewayModelRepository 查询语义（团队行优先于全局同名）。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
from domains.gateway.application.sql_model_catalog import SqlModelCatalogAdapter
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService


@pytest.mark.asyncio
async def test_get_by_name_prefers_team_row_over_global(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    globals_ = await models.list_for_team(None, only_enabled=True)
    if not globals_:
        pytest.skip("catalog sync produced no global models (no provider API keys)")
    cred_id = globals_[0].credential_id
    provider = globals_[0].provider
    virtual = f"dup-test-{uuid.uuid4().hex[:8]}"
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await models.create(
        team_id=None,
        name=virtual,
        capability="chat",
        real_model=globals_[0].real_model,
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "test-dup"},
    )
    await models.create(
        team_id=team.id,
        name=virtual,
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "test-team"},
    )
    await db_session.flush()
    picked = await models.get_by_name(team.id, virtual)
    assert picked is not None
    assert picked.team_id == team.id
    assert picked.real_model == "deepseek/deepseek-chat"


@pytest.mark.asyncio
async def test_list_for_team_orders_team_models_before_global(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    globals_ = await models.list_for_team(None, only_enabled=True)
    if not globals_:
        pytest.skip("catalog sync produced no global models (no provider API keys)")
    cred_id = globals_[0].credential_id
    provider = globals_[0].provider
    virtual = f"order-dup-{uuid.uuid4().hex[:8]}"
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await models.create(
        team_id=None,
        name=virtual,
        capability="chat",
        real_model="openai/gpt-4o",
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "test-order-g"},
    )
    await models.create(
        team_id=team.id,
        name=virtual,
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "test-order-t"},
    )
    await db_session.flush()
    rows = await models.list_for_team(team.id, only_enabled=True)
    dup_rows = [r for r in rows if r.name == virtual]
    assert len(dup_rows) == 2
    assert dup_rows[0].team_id == team.id
    assert dup_rows[1].team_id is None


@pytest.mark.asyncio
async def test_sql_catalog_list_dedupes_team_over_global(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    globals_ = await models.list_for_team(None, only_enabled=True)
    if not globals_:
        pytest.skip("catalog sync produced no global models (no provider API keys)")
    cred_id = globals_[0].credential_id
    provider = globals_[0].provider
    virtual = f"catalog-dup-{uuid.uuid4().hex[:8]}"
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await models.create(
        team_id=None,
        name=virtual,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "catalog-test-g"},
    )
    await models.create(
        team_id=team.id,
        name=virtual,
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "catalog-test-t", "display_name": "Team Override Display"},
    )
    await db_session.flush()
    adapter = SqlModelCatalogAdapter(db_session)
    items = await adapter.list_visible_models(billing_team_id=team.id, model_type=None)
    matches = [i for i in items if i["id"] == virtual]
    assert len(matches) == 1
    assert matches[0]["display_name"] == "Team Override Display"
