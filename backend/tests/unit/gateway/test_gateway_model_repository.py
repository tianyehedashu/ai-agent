"""GatewayModelRepository 查询语义（团队行优先于全局同名）。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
from domains.gateway.application.sql_model_catalog import SqlModelCatalogAdapter
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


@pytest.mark.asyncio
async def test_get_by_name_prefers_team_row_over_global(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    globals_ = await models.list_system(only_enabled=True)
    if not globals_:
        pytest.skip("catalog sync produced no global models (no provider API keys)")
    cred_id = globals_[0].credential_id
    provider = globals_[0].provider
    virtual = f"dup-test-{uuid.uuid4().hex[:8]}"
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    team_cred = await create_tenant_test_credential(
        db_session, team.id, provider=provider, name=f"dup-team-cred-{virtual}"
    )
    await models.create_system(
        name=virtual,
        capability="chat",
        real_model=globals_[0].real_model,
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "test-dup"},
    )
    await models.create(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=team_cred.id,
        provider=provider,
        tags={"managed_by": "test-team"},
    )
    await db_session.flush()
    picked = await models.get_by_name(team.id, virtual)
    assert picked is not None
    assert picked.tenant_id == team.id
    assert picked.real_model == "deepseek/deepseek-chat"


@pytest.mark.asyncio
async def test_list_for_tenant_orders_team_models_before_global(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    globals_ = await models.list_system(only_enabled=True)
    if not globals_:
        pytest.skip("catalog sync produced no global models (no provider API keys)")
    cred_id = globals_[0].credential_id
    provider = globals_[0].provider
    virtual = f"order-dup-{uuid.uuid4().hex[:8]}"
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    team_cred = await create_tenant_test_credential(
        db_session, team.id, provider=provider, name=f"order-team-cred-{virtual}"
    )
    await models.create_system(
        name=virtual,
        capability="chat",
        real_model="openai/gpt-4o",
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "test-order-g"},
    )
    await models.create(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=team_cred.id,
        provider=provider,
        tags={"managed_by": "test-order-t"},
    )
    await db_session.flush()
    rows = await models.list_for_tenant(team.id, only_enabled=True)
    dup_rows = [r for r in rows if r.name == virtual]
    assert len(dup_rows) == 1
    assert dup_rows[0].tenant_id == team.id


@pytest.mark.asyncio
async def test_sql_catalog_list_dedupes_team_over_global(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    globals_ = await models.list_system(only_enabled=True)
    if not globals_:
        pytest.skip("catalog sync produced no global models (no provider API keys)")
    cred_id = globals_[0].credential_id
    provider = globals_[0].provider
    virtual = f"catalog-dup-{uuid.uuid4().hex[:8]}"
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    team_cred = await create_tenant_test_credential(
        db_session, team.id, provider=provider, name=f"catalog-team-cred-{virtual}"
    )
    await models.create_system(
        name=virtual,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=cred_id,
        provider=provider,
        tags={"managed_by": "catalog-test-g"},
    )
    await models.create(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=team_cred.id,
        provider=provider,
        tags={"managed_by": "catalog-test-t", "display_name": "Team Override Display"},
    )
    await db_session.flush()
    adapter = SqlModelCatalogAdapter(db_session)
    items = await adapter.list_visible_models(billing_team_id=team.id, model_type=None)
    matches = [i for i in items if i["id"] == virtual]
    assert len(matches) == 1
    assert matches[0]["display_name"] == "Team Override Display"


@pytest.mark.asyncio
async def test_sql_catalog_excludes_last_test_failed(db_session, test_user) -> None:
    """连通性测试为 failed 的系统模型不进入「可见目录」，与对话选择器语义一致。"""
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    adapter = SqlModelCatalogAdapter(db_session)
    before = await adapter.list_visible_models(billing_team_id=team.id, model_type=None)
    if not before:
        pytest.skip("catalog sync produced no global models (no provider API keys)")
    item_id = before[0]["id"]
    sys_row = await models.get_system_by_name(item_id)
    assert sys_row is not None
    await models.update_system(
        sys_row.id,
        last_test_status="failed",
        last_test_reason="unit: forced failed",
    )
    await db_session.flush()

    after = await adapter.list_visible_models(billing_team_id=team.id, model_type=None)
    ids = {i["id"] for i in after}
    assert item_id not in ids


@pytest.mark.asyncio
async def test_list_for_tenant_none_returns_system_models(db_session) -> None:
    """无计费团队时（如 Listing Studio 未带 X-Team-Id）仍应暴露系统目录行。

    回归：此前 ``team_id is None`` 返回空列表，导致 ``resolve_text_chat_model`` 报
    「无可用文本模型」。
    """
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    system_rows = await models.list_system(only_enabled=True)
    if not system_rows:
        pytest.skip("catalog sync produced no system models (no provider API keys)")

    via_none = await models.list_for_tenant(None, only_enabled=True)
    assert len(via_none) >= 1
    assert {r.name for r in via_none} == {r.name for r in system_rows}

    adapter = SqlModelCatalogAdapter(db_session)
    catalog_items = await adapter.list_visible_models(
        billing_team_id=None,
        model_type="text",
    )
    assert len(catalog_items) >= 1
    assert {i["id"] for i in catalog_items}.issubset({r.name for r in system_rows})


@pytest.mark.asyncio
async def test_list_for_tenant_filters_by_provider(db_session, test_user) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    models = GatewayModelRepository(db_session)
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    all_rows = await models.list_for_tenant(team.id, only_enabled=True)
    if not all_rows:
        pytest.skip("catalog sync produced no global models")
    p = all_rows[0].provider
    filtered = await models.list_for_tenant(team.id, only_enabled=True, provider=p)
    assert all(r.provider == p for r in filtered)
    assert len(filtered) == len([r for r in all_rows if r.provider == p])
