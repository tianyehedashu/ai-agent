"""GatewayManagementWriteService.create_multi_credential_gateway_model

把同一 ``(provider, real_model)`` 一键注册到多个凭据并自动生成 ``GatewayRoute``。
"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential, team_owner_actor_kw


async def _seed_team_creds(db_session, team_id: uuid.UUID, owner_id: uuid.UUID, n: int = 2):
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    creds = []
    team_marker = uuid.uuid4().hex[:6]
    for i in range(n):
        creds.append(
            await cred_repo.create_for_tenant(
                tenant_id=team_id,
                provider="openai",
                name=f"multi-cred-{team_marker}-{i}",
                api_key_encrypted=encrypt_value("sk-fake", encryption_key),
                api_base=None,
                created_by_user_id=owner_id,
            )
        )
    return creds


@pytest.mark.asyncio
async def test_multi_credential_creates_models_and_route(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    cred_a = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name=f"multi-a-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    cred_b = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name=f"multi-b-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    writes = GatewayManagementWriteService(db_session)
    virtual = f"multi-virtual-{uuid.uuid4().hex[:6]}"
    result = await writes.create_multi_credential_gateway_model(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="gpt-4o-mini",
        provider="openai",
        credential_ids=[cred_a.id, cred_b.id],
        is_platform_admin=False,
        **team_owner_actor_kw(test_user),
    )
    await db_session.flush()

    route = result.route
    models = result.models
    assert route.virtual_model == virtual
    assert len(models) == 2
    assert sorted(route.primary_models) == sorted([m.name for m in models])

    model_repo = GatewayModelRepository(db_session)
    creds_used = sorted(m.credential_id for m in models)
    assert creds_used == sorted([cred_a.id, cred_b.id])
    for m in models:
        assert m.name.startswith(virtual + "--")
        round_trip = await model_repo.get_by_name(team.id, m.name)
        assert round_trip is not None


@pytest.mark.asyncio
async def test_multi_credential_rejects_duplicate_credentials(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    creds = await _seed_team_creds(db_session, team.id, test_user.id, 1)
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError):
        await writes.create_multi_credential_gateway_model(
            tenant_id=team.id,
            name=f"dup-{uuid.uuid4().hex[:6]}",
            capability="chat",
            real_model="gpt-4o-mini",
            provider="openai",
            credential_ids=[creds[0].id, creds[0].id],
            is_platform_admin=False,
            **team_owner_actor_kw(test_user),
        )


@pytest.mark.asyncio
async def test_multi_credential_conflict_with_existing_route(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    virtual = f"route-conflict-{uuid.uuid4().hex[:6]}"
    await GatewayRouteRepository(db_session).create(
        tenant_id=team.id, virtual_model=virtual, primary_models=[]
    )
    await db_session.flush()

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await create_tenant_test_credential(
        db_session,
        team.id,
        name=f"conflict-{uuid.uuid4().hex[:6]}",
        created_by_user_id=test_user.id,
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError):
        await writes.create_multi_credential_gateway_model(
            tenant_id=team.id,
            name=virtual,
            capability="chat",
            real_model="gpt-4o-mini",
            provider="openai",
            credential_ids=[cred.id],
            is_platform_admin=False,
            **team_owner_actor_kw(test_user),
        )


# ---------------------------------------------------------------------------
# append_credential_to_existing_model_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_credential_creates_route_when_none_exists(db_session, test_user) -> None:
    """已有单模型、无 Route：重命名旧模型并新建 Route。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    old_cred = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name=f"old-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    new_cred = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name=f"new-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    writes = GatewayManagementWriteService(db_session)
    virtual = f"append-{uuid.uuid4().hex[:6]}"
    await writes.create_gateway_model(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=old_cred.id,
        provider="openai",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
        reload_router=False,
    )
    await db_session.flush()

    new_model = await writes.append_credential_to_existing_model_name(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=new_cred.id,
        provider="openai",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        upstream_call_shape=None,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )
    await db_session.flush()

    assert new_model.name.startswith(virtual + "--")
    route_repo = GatewayRouteRepository(db_session)
    route = await route_repo.get_by_virtual_model(team.id, virtual)
    assert route is not None
    assert new_model.name in route.primary_models
    model_repo = GatewayModelRepository(db_session)
    old_renamed = await model_repo.get_by_name(team.id, route.primary_models[0])
    assert old_renamed is not None
    assert old_renamed.name != virtual


@pytest.mark.asyncio
async def test_append_credential_adds_to_existing_route(db_session, test_user) -> None:
    """已有 Route：直接追加新凭据别名到 primary_models。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    creds = []
    for i in range(3):
        creds.append(
            await cred_repo.create_for_tenant(
                tenant_id=team.id,
                provider="openai",
                name=f"route-append-{i}-{uuid.uuid4().hex[:6]}",
                api_key_encrypted=encrypt_value("sk-fake", encryption_key),
                api_base=None,
                created_by_user_id=test_user.id,
            )
        )
    writes = GatewayManagementWriteService(db_session)
    virtual = f"route-append-{uuid.uuid4().hex[:6]}"
    await writes.create_multi_credential_gateway_model(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="gpt-4o-mini",
        provider="openai",
        credential_ids=[creds[0].id, creds[1].id],
        is_platform_admin=False,
        **team_owner_actor_kw(test_user),
    )
    await db_session.flush()

    new_model = await writes.append_credential_to_existing_model_name(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=creds[2].id,
        provider="openai",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        upstream_call_shape=None,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )
    await db_session.flush()

    route_repo = GatewayRouteRepository(db_session)
    route = await route_repo.get_by_virtual_model(team.id, virtual)
    assert route is not None
    assert len(route.primary_models) == 3
    assert new_model.name in route.primary_models


@pytest.mark.asyncio
async def test_append_credential_rejects_mismatched_real_model(db_session, test_user) -> None:
    """real_model 不一致时拒绝追加。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    old_cred = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name=f"mismatch-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    new_cred = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name=f"mismatch-new-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    writes = GatewayManagementWriteService(db_session)
    virtual = f"mismatch-{uuid.uuid4().hex[:6]}"
    await writes.create_gateway_model(
        tenant_id=team.id,
        name=virtual,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=old_cred.id,
        provider="openai",
        weight=1,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
        reload_router=False,
    )
    await db_session.flush()

    with pytest.raises(ValidationError):
        await writes.append_credential_to_existing_model_name(
            tenant_id=team.id,
            name=virtual,
            capability="chat",
            real_model="gpt-4o",
            credential_id=new_cred.id,
            provider="openai",
            weight=1,
            rpm_limit=None,
            tpm_limit=None,
            tags=None,
            upstream_call_shape=None,
            actor_user_id=test_user.id,
            team_role="owner",
            is_platform_admin=False,
        )
