"""虚拟模型名引用修剪（vkey / 路由）。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.application.model_reference_prune import prune_gateway_model_name_references
from domains.gateway.domain.virtual_key_service import generate_vkey
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential, team_owner_actor_kw


@pytest.mark.asyncio
async def test_delete_gateway_model_prunes_vkey_allowed_list(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team.id, name="prune-test-cred")
    model_name = f"prune-vm-{uuid.uuid4().hex[:6]}"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=model_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    vkey_repo = VirtualKeyRepository(db_session)
    _, key_id, key_hash = generate_vkey()
    await vkey_repo.create(
        tenant_id=team.id,
        created_by_user_id=test_user.id,
        name=f"vkey-{uuid.uuid4().hex[:6]}",
        description=None,
        key_id_str=key_id,
        key_hash=key_hash,
        encrypted_key="encrypted",
        allowed_models=[model_name, "other-model"],
        allowed_capabilities=[],
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    await writes.delete_gateway_model(
        model.id, tenant_id=team.id, **team_owner_actor_kw(test_user)
    )
    await db_session.flush()

    keys = await vkey_repo.list_for_tenant(team.id, include_inactive=True)
    assert keys
    allowed = list(keys[0].allowed_models or [])
    assert model_name not in allowed
    assert "other-model" in allowed


@pytest.mark.asyncio
async def test_prune_gateway_model_name_references_updates_routes(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    route_repo = GatewayRouteRepository(db_session)
    gone = f"gone-{uuid.uuid4().hex[:6]}"
    stay = f"stay-{uuid.uuid4().hex[:6]}"
    route = await route_repo.create(
        tenant_id=team.id,
        virtual_model="router-test",
        primary_models=[gone, stay],
        fallbacks_general=[gone],
    )
    await db_session.flush()

    _, routes_updated = await prune_gateway_model_name_references(db_session, frozenset({gone}))
    assert routes_updated >= 1
    refreshed = await route_repo.get(route.id)
    assert refreshed is not None
    assert gone not in (refreshed.primary_models or [])
    assert stay in (refreshed.primary_models or [])
    assert gone not in (refreshed.fallbacks_general or [])
