"""GatewayRoute 引用完整性审计单测。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.route_audit import audit_gateway_routes
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


@pytest.mark.asyncio
async def test_audit_clean_when_all_references_exist(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team.id,
        provider="openai",
        name=f"audit-clean-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    model_a = await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=f"vm-a-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    model_b = await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=f"vm-b-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await GatewayRouteRepository(db_session).create(
        team_id=team.id,
        virtual_model=f"vroute-{uuid.uuid4().hex[:6]}",
        primary_models=[model_a.name, model_b.name],
        fallbacks_general=[model_b.name],
    )
    await db_session.flush()

    report = await audit_gateway_routes(db_session)
    assert report.is_clean
    assert not report.has_blocking_issues
    assert report.total_routes >= 1
    assert report.issues == []


@pytest.mark.asyncio
async def test_audit_reports_missing_primary_and_fallback_names(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team.id,
        provider="openai",
        name=f"audit-bad-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    real = await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=f"vm-real-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    virtual = f"vroute-{uuid.uuid4().hex[:6]}"
    missing = f"vm-missing-{uuid.uuid4().hex[:6]}"
    await GatewayRouteRepository(db_session).create(
        team_id=team.id,
        virtual_model=virtual,
        primary_models=[real.name, missing],
        fallbacks_general=[missing],
    )
    await db_session.flush()

    report = await audit_gateway_routes(db_session)
    fields_with_missing = {
        (i.virtual_model, i.field, i.missing_names) for i in report.issues
    }
    assert (virtual, "primary_models", (missing,)) in fields_with_missing
    assert (virtual, "fallbacks_general", (missing,)) in fields_with_missing


@pytest.mark.asyncio
async def test_audit_flags_virtual_model_shadowed_by_gateway_model(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team.id,
        provider="openai",
        name=f"audit-shadow-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    same = f"shared-{uuid.uuid4().hex[:6]}"
    real = await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=same,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await GatewayRouteRepository(db_session).create(
        team_id=team.id,
        virtual_model=same,
        primary_models=[real.name],
    )
    await db_session.flush()

    report = await audit_gateway_routes(db_session)
    assert (str(team.id), same) in report.virtual_model_shadowed_by_model
