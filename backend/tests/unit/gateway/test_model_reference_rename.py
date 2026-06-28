"""虚拟模型名引用重命名（vkey / 路由，团队作用域）。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.application.catalog.model_reference_prune import rename_gateway_model_name_references
from domains.gateway.domain.vkey.virtual_key_service import generate_vkey
from domains.gateway.infrastructure.repositories.model_repository import (
    GatewayModelRepository,
    GatewayRouteRepository,
)
from domains.gateway.infrastructure.repositories.virtual_key_repository import VirtualKeyRepository
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential, team_owner_actor_kw


@pytest.mark.asyncio
async def test_rename_references_updates_team_vkey_and_route(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await create_tenant_test_credential(db_session, team.id, name="rename-test-cred")
    old_name = f"rename-old-{uuid.uuid4().hex[:6]}"
    new_name = f"rename-new-{uuid.uuid4().hex[:6]}"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=old_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    route_repo = GatewayRouteRepository(db_session)
    route = await route_repo.create(
        tenant_id=team.id,
        virtual_model="rename-router",
        primary_models=[old_name, "other-stay"],
        fallbacks_general=[old_name],
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
        allowed_models=[old_name, "other-stay"],
        allowed_capabilities=[],
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
    )
    await db_session.flush()

    vkeys_updated, routes_updated = await rename_gateway_model_name_references(
        db_session,
        tenant_id=team.id,
        old_name=old_name,
        new_name=new_name,
    )
    assert vkeys_updated >= 1
    assert routes_updated >= 1

    keys = await vkey_repo.list_for_tenant(team.id, include_inactive=True)
    allowed = list(keys[0].allowed_models or [])
    assert old_name not in allowed
    assert new_name in allowed
    assert "other-stay" in allowed

    refreshed_route = await route_repo.get(route.id)
    assert refreshed_route is not None
    assert old_name not in (refreshed_route.primary_models or [])
    assert new_name in (refreshed_route.primary_models or [])
    assert old_name not in (refreshed_route.fallbacks_general or [])
    assert model.id  # silence unused in assert block


@pytest.mark.asyncio
async def test_rename_references_does_not_touch_other_team(db_session, test_user) -> None:
    team_a = await TeamService(db_session).ensure_personal_team(test_user.id)
    other_user = User(
        email=f"other_{uuid.uuid4()}@example.com",
        hashed_password="hashed_password",
        name="Other User",
    )
    db_session.add(other_user)
    await db_session.flush()
    team_b = await TeamService(db_session).ensure_personal_team(other_user.id)
    shared_name = f"shared-{uuid.uuid4().hex[:6]}"
    vkey_repo = VirtualKeyRepository(db_session)
    _, key_id_b, key_hash_b = generate_vkey()
    await vkey_repo.create(
        tenant_id=team_b.id,
        created_by_user_id=other_user.id,
        name=f"vkey-b-{uuid.uuid4().hex[:6]}",
        description=None,
        key_id_str=key_id_b,
        key_hash=key_hash_b,
        encrypted_key="encrypted",
        allowed_models=[shared_name],
        allowed_capabilities=[],
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
    )
    await db_session.flush()

    new_name = f"renamed-{uuid.uuid4().hex[:6]}"
    await rename_gateway_model_name_references(
        db_session,
        tenant_id=team_a.id,
        old_name=shared_name,
        new_name=new_name,
    )
    await db_session.flush()

    keys_b = await vkey_repo.list_for_tenant(team_b.id, include_inactive=True)
    assert shared_name in (keys_b[0].allowed_models or [])
    assert new_name not in (keys_b[0].allowed_models or [])


@pytest.mark.asyncio
async def test_update_gateway_model_renames_with_cascade(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await create_tenant_test_credential(db_session, team.id, name="update-rename-cred")
    old_name = f"upd-old-{uuid.uuid4().hex[:6]}"
    new_name = f"upd-new-{uuid.uuid4().hex[:6]}"
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=old_name,
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
        allowed_models=[old_name],
        allowed_capabilities=[],
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    updated = await writes.update_gateway_model(
        model.id,
        tenant_id=team.id,
        is_platform_admin=False,
        fields={"name": new_name},
        **team_owner_actor_kw(test_user),
    )
    assert updated.name == new_name

    keys = await vkey_repo.list_for_tenant(team.id, include_inactive=True)
    assert new_name in (keys[0].allowed_models or [])
    assert old_name not in (keys[0].allowed_models or [])


@pytest.mark.asyncio
async def test_update_gateway_model_name_conflict(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await create_tenant_test_credential(db_session, team.id, name="conflict-cred")
    taken_name = f"taken-{uuid.uuid4().hex[:6]}"
    await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=taken_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=f"other-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError, match="注册别名已存在"):
        await writes.update_gateway_model(
            model.id,
            tenant_id=team.id,
            is_platform_admin=False,
            fields={"name": taken_name},
            **team_owner_actor_kw(test_user),
        )


@pytest.mark.asyncio
async def test_update_global_gateway_model_name_conflict(db_session) -> None:
    from bootstrap.config import settings
    from domains.gateway.infrastructure.repositories.system_credential_repository import (
        SystemProviderCredentialRepository,
    )
    from libs.crypto import derive_encryption_key

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-conflict-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
    )
    taken_name = f"global-taken-{uuid.uuid4().hex[:6]}"
    model_repo = GatewayModelRepository(db_session)
    await model_repo.create_system(
        name=taken_name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    model = await model_repo.create_system(
        name=f"global-other-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    await db_session.flush()

    assert await model_repo.name_exists_in_scope(None, taken_name, exclude_id=model.id)
