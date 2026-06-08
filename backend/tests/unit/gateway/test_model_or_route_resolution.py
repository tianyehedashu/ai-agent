"""model_or_route_resolution.resolve_model_or_route 行为。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.model_or_route_resolution import (
    GatewayModelResolveSnapshot,
    resolve_model_or_route,
)
from domains.gateway.application.resolve_model_cache import clear_resolve_model_cache_for_tests
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


async def _seed_cred(db_session, team_id, name):
    return await create_tenant_test_credential(db_session, team_id, name=name)


@pytest.mark.asyncio
async def test_resolve_returns_gateway_model_when_name_matches(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await _seed_cred(db_session, team.id, f"resolve-direct-{uuid.uuid4().hex[:6]}")
    name = f"vm-direct-{uuid.uuid4().hex[:6]}"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
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
async def test_resolve_cache_returns_snapshot_after_session_expunge(
    db_session, test_user, monkeypatch
) -> None:
    """缓存命中不应返回 SQLAlchemy ORM 实例，避免 Session 关闭后属性刷新失败。"""
    monkeypatch.setattr(settings, "gateway_resolve_model_cache_enabled", True)
    clear_resolve_model_cache_for_tests()
    try:
        team = await TeamService(db_session).ensure_personal_team(test_user.id)
        cred = await _seed_cred(db_session, team.id, f"resolve-cache-{uuid.uuid4().hex[:6]}")
        name = f"vm-cache-{uuid.uuid4().hex[:6]}"
        model = await GatewayModelRepository(db_session).create(
            tenant_id=team.id,
            name=name,
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="openai",
        )
        await db_session.flush()
        model_id = model.id

        first = await resolve_model_or_route(db_session, team.id, name)
        assert first is not None
        assert first.record.id == model_id

        db_session.sync_session.expunge_all()

        second = await resolve_model_or_route(db_session, team.id, name)
        assert second is not None
        assert isinstance(second.record, GatewayModelResolveSnapshot)
        assert second.record.id == model_id
        assert second.record.provider == "openai"
        assert second.record.real_model == "gpt-4o-mini"
    finally:
        clear_resolve_model_cache_for_tests()


@pytest.mark.asyncio
async def test_resolve_returns_route_with_primary_model(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await _seed_cred(db_session, team.id, f"resolve-route-{uuid.uuid4().hex[:6]}")
    primary_name = f"vm-primary-{uuid.uuid4().hex[:6]}"
    virtual = f"vroute-{uuid.uuid4().hex[:6]}"
    primary = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=primary_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await GatewayRouteRepository(db_session).create(
        tenant_id=team.id,
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
        tenant_id=team.id,
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


@pytest.mark.asyncio
async def test_resolve_personal_model_via_shared_team_context(db_session, test_user) -> None:
    """共享团队 vkey 试调个人凭据模型时，应解析到 personal team 注册行。"""
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    from bootstrap.config import settings
    from domains.gateway.infrastructure.repositories.credential_repository import (
        ProviderCredentialRepository,
    )
    from libs.crypto import derive_encryption_key, encrypt_value

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="user",
        scope_id=test_user.id,
        provider="volcengine",
        name=f"personal-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    alias = f"deepseek-v3-2-{uuid.uuid4().hex[:6]}-chat"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=personal.id,
        name=alias,
        capability="chat",
        real_model="deepseek-v3-2",
        credential_id=cred.id,
        provider="volcengine",
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, shared.id, alias, user_id=test_user.id)
    assert resolved is not None
    assert resolved.route is None
    assert resolved.record.id == model.id
    assert resolved.record.tenant_id == personal.id


@pytest.mark.asyncio
async def test_resolve_personal_when_shared_has_disabled_duplicate(db_session, test_user) -> None:
    """共享团队存在同名 disabled 模型时，应回退到 personal team 注册行。"""
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-dup-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    shared_cred = await _seed_cred(db_session, shared.id, f"shared-{uuid.uuid4().hex[:6]}")
    personal_cred = await _seed_cred(db_session, personal.id, f"personal-{uuid.uuid4().hex[:6]}")
    alias = f"deepseek-dup-{uuid.uuid4().hex[:6]}-chat"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared.id,
        name=alias,
        capability="chat",
        real_model="deepseek-v3-2",
        credential_id=shared_cred.id,
        provider="volcengine",
        enabled=False,
    )
    personal_model = await GatewayModelRepository(db_session).create(
        tenant_id=personal.id,
        name=alias,
        capability="chat",
        real_model="deepseek-v3-2",
        credential_id=personal_cred.id,
        provider="volcengine",
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, shared.id, alias, user_id=test_user.id)
    assert resolved is not None
    assert resolved.record.id == personal_model.id
    assert resolved.record.tenant_id == personal.id


@pytest.mark.asyncio
async def test_resolve_prefers_personal_when_shared_has_enabled_duplicate(
    db_session, test_user
) -> None:
    """共享团队同名 enabled 模型存在时，有 user_id 仍优先 personal team（Playground BYOK）。"""
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-enabled-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    shared_cred = await _seed_cred(db_session, shared.id, f"shared-{uuid.uuid4().hex[:6]}")
    personal_cred = await _seed_cred(db_session, personal.id, f"personal-{uuid.uuid4().hex[:6]}")
    alias = f"deepseek-enabled-{uuid.uuid4().hex[:6]}-chat"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared.id,
        name=alias,
        capability="chat",
        real_model="deepseek-v3-2",
        credential_id=shared_cred.id,
        provider="volcengine",
        enabled=True,
    )
    personal_model = await GatewayModelRepository(db_session).create(
        tenant_id=personal.id,
        name=alias,
        capability="chat",
        real_model="deepseek-v3-2",
        credential_id=personal_cred.id,
        provider="volcengine",
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, shared.id, alias, user_id=test_user.id)
    assert resolved is not None
    assert resolved.record.id == personal_model.id
    assert resolved.record.tenant_id == personal.id


@pytest.mark.asyncio
async def test_resolve_personal_when_shared_has_inactive_credential(db_session, test_user) -> None:
    """共享团队同名 enabled 模型但凭据 inactive 时，应回退 personal team。"""
    teams = TeamService(db_session)
    personal = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-inactive-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    from bootstrap.config import settings
    from domains.gateway.infrastructure.repositories.credential_repository import (
        ProviderCredentialRepository,
    )
    from libs.crypto import derive_encryption_key, encrypt_value

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    inactive_cred = await ProviderCredentialRepository(db_session).create(
        tenant_id=shared.id,
        provider="volcengine",
        name=f"inactive-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        is_active=False,
    )
    personal_cred = await _seed_cred(db_session, personal.id, f"personal-{uuid.uuid4().hex[:6]}")
    alias = f"deepseek-inactive-{uuid.uuid4().hex[:6]}-chat"
    await GatewayModelRepository(db_session).create(
        tenant_id=shared.id,
        name=alias,
        capability="chat",
        real_model="deepseek-v3-2",
        credential_id=inactive_cred.id,
        provider="volcengine",
    )
    personal_model = await GatewayModelRepository(db_session).create(
        tenant_id=personal.id,
        name=alias,
        capability="chat",
        real_model="deepseek-v3-2",
        credential_id=personal_cred.id,
        provider="volcengine",
    )
    await db_session.flush()

    resolved = await resolve_model_or_route(db_session, shared.id, alias, user_id=test_user.id)
    assert resolved is not None
    assert resolved.record.id == personal_model.id
    assert resolved.record.tenant_id == personal.id
