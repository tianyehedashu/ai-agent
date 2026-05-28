"""GET /teams/{id}/models?registry_scope= 语义与权限。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
from domains.gateway.application.management import GatewayManagementReadService
from domains.gateway.domain.policies.model_selection import registry_kind_for_merged_row
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


async def _seed_byok_and_team_models(
    db_session,
    test_user,
) -> tuple[uuid.UUID, str, str]:
    """personal team 上各一条 BYOK 与 team-scope 注册模型，返回 (tenant_id, byok_name, team_name)。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    model_repo = GatewayModelRepository(db_session)
    user_cred = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="openai",
        name=f"byok-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake-byok", encryption_key),
        api_base=None,
    )
    team_cred = await create_tenant_test_credential(
        db_session,
        team.id,
        name=f"team-{uuid.uuid4().hex[:6]}",
    )
    byok_name = f"byok-model-{uuid.uuid4().hex[:6]}"
    team_name = f"team-model-{uuid.uuid4().hex[:6]}"
    await model_repo.create(
        tenant_id=team.id,
        name=byok_name,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=user_cred.id,
        provider="openai",
    )
    await model_repo.create(
        tenant_id=team.id,
        name=team_name,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=team_cred.id,
        provider="openai",
    )
    await db_session.flush()
    return team.id, byok_name, team_name


@pytest.mark.asyncio
async def test_list_gateway_models_registry_scope_team_excludes_system(
    db_session, test_user
) -> None:
    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    reads = GatewayManagementReadService(db_session)

    callable_rows = await reads.list_gateway_models(
        team.id, registry_scope="callable", only_enabled=True
    )
    team_rows = await reads.list_gateway_models(team.id, registry_scope="team", only_enabled=False)
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


@pytest.mark.asyncio
async def test_team_scope_excludes_user_byok_models(db_session, test_user) -> None:
    tenant_id, byok_name, team_name = await _seed_byok_and_team_models(db_session, test_user)
    reads = GatewayManagementReadService(db_session)
    team_rows = await reads.list_gateway_models(
        tenant_id, registry_scope="team", only_enabled=False
    )
    names = {r.name for r in team_rows}
    assert byok_name not in names
    assert team_name in names


@pytest.mark.asyncio
async def test_team_scope_keeps_team_credential_bindings_on_shared_team(
    db_session, test_user
) -> None:
    teams = TeamService(db_session)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    team_cred = await create_tenant_test_credential(
        db_session,
        shared.id,
        name=f"shared-cred-{uuid.uuid4().hex[:6]}",
    )
    team_name = f"shared-model-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared.id,
        name=team_name,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=team_cred.id,
        provider="openai",
    )
    await db_session.flush()
    reads = GatewayManagementReadService(db_session)
    team_rows = await reads.list_gateway_models(
        shared.id, registry_scope="team", only_enabled=False
    )
    assert team_name in {r.name for r in team_rows}


@pytest.mark.asyncio
async def test_callable_scope_still_includes_byok(db_session, test_user) -> None:
    tenant_id, byok_name, team_name = await _seed_byok_and_team_models(db_session, test_user)
    reads = GatewayManagementReadService(db_session)
    callable_rows = await reads.list_gateway_models(
        tenant_id, registry_scope="callable", only_enabled=False
    )
    names = {r.name for r in callable_rows}
    assert byok_name in names
    assert team_name in names
