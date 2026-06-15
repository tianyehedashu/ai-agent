"""copy_models_to_team 写服务单元测试。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


async def _create_user_credential(db_session, user: User, *, name: str):
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    return await ProviderCredentialRepository(db_session).create(
        scope="user",
        scope_id=user.id,
        provider="openai",
        name=name,
        api_key_encrypted=encrypt_value("sk-copy-models-test", encryption_key),
    )


async def _create_team_credential(
    db_session,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    name: str,
):
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    return await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=tenant_id,
        provider="openai",
        name=name,
        api_key_encrypted=encrypt_value("sk-team-copy-models", encryption_key),
        created_by_user_id=actor_id,
    )


async def _create_team_model(db_session, tenant_id, credential, *, name: str):
    return await GatewayModelRepository(db_session).create(
        tenant_id=tenant_id,
        name=name,
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=credential.id,
        provider=credential.provider,
        weight=1,
        created_by_user_id=credential.created_by_user_id,
    )


@pytest.mark.asyncio
async def test_copy_personal_models_subset_to_team_existing_cred(
    db_session, test_user: User
) -> None:
    personal_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    target_team = await TeamService(db_session).create_team(
        name="model-copy-target",
        slug=f"model-copy-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    src_cred = await _create_user_credential(db_session, test_user, name="personal-openai")
    model_a = await GatewayModelRepository(db_session).create(
        tenant_id=personal_team.id,
        name="pick-a",
        capability="chat",
        real_model="openai/gpt-4o",
        credential_id=src_cred.id,
        provider="openai",
        weight=1,
    )
    await GatewayModelRepository(db_session).create(
        tenant_id=personal_team.id,
        name="skip-b",
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=src_cred.id,
        provider="openai",
        weight=1,
    )
    dest_cred = await _create_team_credential(
        db_session,
        tenant_id=target_team.id,
        actor_id=test_user.id,
        name="dest-openai",
    )
    await db_session.commit()

    from domains.gateway.application.management.model_copy_types import ModelCopyCredentialPlan

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_models_to_team(
        model_ids=[model_a.id],
        destination_team_id=target_team.id,
        credential_plans=[
            ModelCopyCredentialPlan(
                source_credential_id=src_cred.id,
                mode="existing",
                destination_credential_id=dest_cred.id,
            )
        ],
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
        platform_user_role="user",
    )

    assert len(result.succeeded) == 1
    assert result.failed == []
    assert result.succeeded[0].source_model_id == str(model_a.id)

    team_models = await GatewayModelRepository(db_session).list_tenant_owned(target_team.id)
    assert len(team_models) == 1
    assert team_models[0].name == "pick-a"


@pytest.mark.asyncio
async def test_copy_team_models_copy_credential_mode(db_session, test_user: User) -> None:
    source_team = await TeamService(db_session).create_team(
        name="model-copy-source",
        slug=f"model-copy-src-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    target_team = await TeamService(db_session).create_team(
        name="model-copy-dest",
        slug=f"model-copy-dst-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    src_cred = await _create_team_credential(
        db_session,
        tenant_id=source_team.id,
        actor_id=test_user.id,
        name="src-openai",
    )
    model = await _create_team_model(
        db_session, source_team.id, src_cred, name="team-model-1"
    )
    await db_session.commit()

    from domains.gateway.application.management.model_copy_types import ModelCopyCredentialPlan

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_models_to_team(
        model_ids=[model.id],
        destination_team_id=target_team.id,
        credential_plans=[
            ModelCopyCredentialPlan(
                source_credential_id=src_cred.id,
                mode="copy_credential",
            )
        ],
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
        platform_user_role="user",
    )

    assert len(result.succeeded) == 1
    team_creds = await ProviderCredentialRepository(db_session).list_for_tenant(target_team.id)
    assert len(team_creds) == 1
    team_models = await GatewayModelRepository(db_session).list_tenant_owned(target_team.id)
    assert len(team_models) == 1


@pytest.mark.asyncio
async def test_copy_denied_for_other_user_team_credential(
    db_session, test_user: User
) -> None:
    other = User(
        email=f"copy_model_other_{uuid.uuid4()}@example.com",
        hashed_password="hashed_password",
        name="Other",
    )
    db_session.add(other)
    await db_session.flush()

    source_team = await TeamService(db_session).create_team(
        name="model-copy-deny-src",
        slug=f"model-copy-deny-{uuid.uuid4().hex[:8]}",
        owner_user_id=other.id,
    )
    target_team = await TeamService(db_session).create_team(
        name="model-copy-deny-dst",
        slug=f"model-copy-deny-d-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await TeamService(db_session).add_member(source_team.id, test_user.id, role="admin")
    await db_session.commit()

    src_cred = await _create_team_credential(
        db_session,
        tenant_id=source_team.id,
        actor_id=other.id,
        name="private-openai",
    )
    model = await _create_team_model(
        db_session, source_team.id, src_cred, name="private-model"
    )
    await db_session.commit()

    from domains.gateway.application.management.model_copy_types import ModelCopyCredentialPlan

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_models_to_team(
        model_ids=[model.id],
        destination_team_id=target_team.id,
        credential_plans=[
            ModelCopyCredentialPlan(
                source_credential_id=src_cred.id,
                mode="copy_credential",
            )
        ],
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
        platform_user_role="user",
    )

    assert result.succeeded == []
    assert len(result.failed) == 1
    assert result.failed[0].reason == "credential not found"


@pytest.mark.asyncio
async def test_copy_credential_rolls_back_dest_cred_when_all_models_fail(
    db_session, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    personal_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    target_team = await TeamService(db_session).create_team(
        name="model-copy-rollback",
        slug=f"model-copy-rb-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    src_cred = await _create_user_credential(db_session, test_user, name="rollback-src")
    model = await GatewayModelRepository(db_session).create(
        tenant_id=personal_team.id,
        name="rollback-model",
        capability="chat",
        real_model="openai/gpt-4o",
        credential_id=src_cred.id,
        provider="openai",
        weight=1,
    )
    await db_session.commit()

    from domains.gateway.application.management.model_copy_types import ModelCopyCredentialPlan

    writes = GatewayManagementWriteService(db_session)

    async def fail_create(*_args: object, **_kwargs: object) -> object:
        from libs.exceptions import ValidationError

        raise ValidationError("forced model create failure")

    monkeypatch.setattr(writes._models, "create", fail_create)

    result = await writes.copy_models_to_team(
        model_ids=[model.id],
        destination_team_id=target_team.id,
        credential_plans=[
            ModelCopyCredentialPlan(
                source_credential_id=src_cred.id,
                mode="copy_credential",
            )
        ],
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
        platform_user_role="user",
    )

    assert result.succeeded == []
    assert len(result.failed) == 1
    team_creds = await ProviderCredentialRepository(db_session).list_for_tenant(target_team.id)
    assert team_creds == []
