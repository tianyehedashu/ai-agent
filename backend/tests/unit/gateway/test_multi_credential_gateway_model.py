"""GatewayManagementWriteService.create_multi_credential_gateway_model

把同一 ``(provider, real_model)`` 一键注册到多个凭据并自动生成 ``GatewayRoute``。
"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential
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


async def _seed_team_creds(db_session, n: int = 2):
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    creds = []
    team_marker = uuid.uuid4().hex[:6]
    for i in range(n):
        creds.append(
            await cred_repo.create_for_tenant(
                tenant_id=uuid.uuid4(),
                provider="openai",
                name=f"multi-cred-{team_marker}-{i}",
                api_key_encrypted=encrypt_value("sk-fake", encryption_key),
                api_base=None,
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
    )
    cred_b = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name=f"multi-b-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
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
    creds = await _seed_team_creds(db_session, 1)
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
    cred = await create_tenant_test_credential(db_session, team.id, name=f"conflict-{uuid.uuid4().hex[:6]}")
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
        )
