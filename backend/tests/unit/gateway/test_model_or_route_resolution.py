"""model_or_route_resolution.resolve_model_or_route 行为。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.model_or_route_resolution import resolve_model_or_route
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


async def _seed_cred(db_session, team_id, name):
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    return await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team_id,
        provider="openai",
        name=name,
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )


@pytest.mark.asyncio
async def test_resolve_returns_gateway_model_when_name_matches(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await _seed_cred(db_session, team.id, f"resolve-direct-{uuid.uuid4().hex[:6]}")
    name = f"vm-direct-{uuid.uuid4().hex[:6]}"
    model = await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, team.id, name)
    assert resolved is not None
    assert resolved.route is None
    assert resolved.via_route is None
    assert resolved.record.id == model.id


@pytest.mark.asyncio
async def test_resolve_returns_route_with_primary_model(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await _seed_cred(db_session, team.id, f"resolve-route-{uuid.uuid4().hex[:6]}")
    primary_name = f"vm-primary-{uuid.uuid4().hex[:6]}"
    virtual = f"vroute-{uuid.uuid4().hex[:6]}"
    primary = await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=primary_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await GatewayRouteRepository(db_session).create(
        team_id=team.id,
        virtual_model=virtual,
        primary_models=[primary_name],
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, team.id, virtual)
    assert resolved is not None
    assert resolved.route is not None
    assert resolved.via_route == virtual
    assert resolved.record.id == primary.id


@pytest.mark.asyncio
async def test_resolve_returns_none_when_route_primary_missing(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    virtual = f"empty-route-{uuid.uuid4().hex[:6]}"
    await GatewayRouteRepository(db_session).create(
        team_id=team.id,
        virtual_model=virtual,
        primary_models=[f"ghost-{uuid.uuid4().hex[:6]}"],
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, team.id, virtual)
    assert resolved is None


@pytest.mark.asyncio
async def test_resolve_returns_none_when_name_unknown(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    resolved = await resolve_model_or_route(db_session, team.id, "no-such-thing")
    assert resolved is None
