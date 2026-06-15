"""个人凭据 + 关联模型批量导入到团队。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.application.management.credential_copy_types import (
    ImportCredentialsWithModelsResult,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


async def _create_user_credential(
    db_session, user: User, *, provider: str = "openai", name: str
):
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    return await ProviderCredentialRepository(db_session).create(
        scope="user",
        scope_id=user.id,
        provider=provider,
        name=name,
        api_key_encrypted=encrypt_value("sk-fake-import-test", encryption_key),
    )


async def _create_personal_model(db_session, tenant_id, credential, *, name: str, real_model: str):
    repo = GatewayModelRepository(db_session)
    return await repo.create(
        tenant_id=tenant_id,
        name=name,
        capability="chat",
        real_model=real_model,
        credential_id=credential.id,
        provider=credential.provider,
        weight=1,
        tags={"display_name": name},
    )


@pytest.mark.asyncio
async def test_import_credential_with_models_success(db_session, test_user: User) -> None:
    """1 个凭据 + 2 个关联模型成功导入到目标团队。"""
    personal_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    target_team = await TeamService(db_session).create_team(
        name="import-target-team",
        slug=f"import-target-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    cred = await _create_user_credential(db_session, test_user, name="my-openai-key")
    await _create_personal_model(
        db_session, personal_team.id, cred, name="gpt-4o", real_model="openai/gpt-4o"
    )
    await _create_personal_model(
        db_session, personal_team.id, cred, name="gpt-4o-mini", real_model="openai/gpt-4o-mini"
    )
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.import_credentials_with_models_to_team(
        credential_ids=[cred.id],
        tenant_id=target_team.id,
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
    )

    assert isinstance(result, ImportCredentialsWithModelsResult)
    assert len(result.succeeded) == 1
    assert len(result.failed) == 0

    item = result.succeeded[0]
    assert item.source_credential_id == cred.id
    assert item.provider == "openai"
    assert item.new_credential_name == "my-openai-key"
    assert len(item.models_created) == 2
    assert len(item.models_failed) == 0

    # Verify team-side data
    team_creds = await ProviderCredentialRepository(db_session).list_for_tenant(target_team.id)
    assert len(team_creds) == 1
    assert team_creds[0].name == "my-openai-key"

    model_repo = GatewayModelRepository(db_session)
    team_models = await model_repo.list_tenant_owned(target_team.id)
    assert len(team_models) == 2
    names = {m.name for m in team_models}
    assert "gpt-4o" in names
    assert "gpt-4o-mini" in names


@pytest.mark.asyncio
async def test_import_credential_name_conflict_auto_rename(
    db_session, test_user: User
) -> None:
    """目标团队已有同名凭据 → 自动追加 -imported-xxxx 后缀。"""
    personal_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    target_team = await TeamService(db_session).create_team(
        name="import-conflict-team",
        slug=f"import-conflict-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    # Pre-create a team credential with the same provider+name
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=target_team.id,
        provider="openai",
        name="dup-cred",
        api_key_encrypted=encrypt_value("sk-existing", encryption_key),
    )
    await db_session.commit()

    cred = await _create_user_credential(db_session, test_user, name="dup-cred")
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.import_credentials_with_models_to_team(
        credential_ids=[cred.id],
        tenant_id=target_team.id,
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 1
    assert result.succeeded[0].new_credential_name.startswith("dup-cred-imported-")


@pytest.mark.asyncio
async def test_import_model_name_conflict_auto_rename(
    db_session, test_user: User
) -> None:
    """目标团队已有同名模型 → 追加数字后缀。"""
    personal_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    target_team = await TeamService(db_session).create_team(
        name="import-model-conflict",
        slug=f"import-mc-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    cred = await _create_user_credential(db_session, test_user, name="model-conflict-cred")

    # Create personal model
    await _create_personal_model(
        db_session, personal_team.id, cred, name="conflict-model", real_model="openai/gpt-4o"
    )

    # Pre-create same-named model in target team under a different credential
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    other_cred = await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=target_team.id,
        provider="openai",
        name="other-cred",
        api_key_encrypted=encrypt_value("sk-other", encryption_key),
    )
    model_repo = GatewayModelRepository(db_session)
    await model_repo.create(
        tenant_id=target_team.id,
        name="conflict-model",
        capability="chat",
        real_model="openai/gpt-4o",
        credential_id=other_cred.id,
        provider="openai",
    )
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.import_credentials_with_models_to_team(
        credential_ids=[cred.id],
        tenant_id=target_team.id,
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 1
    item = result.succeeded[0]
    assert len(item.models_created) == 1
    assert item.models_created[0].name == "conflict-model-2"


@pytest.mark.asyncio
async def test_import_non_user_scope_credential_fails(
    db_session, test_user: User
) -> None:
    """非 user-scope 凭据 → 失败记录。"""
    target_team = await TeamService(db_session).create_team(
        name="import-scope-team",
        slug=f"import-scope-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    # Create a team-scope credential
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    team_cred = await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=target_team.id,
        provider="openai",
        name="team-cred",
        api_key_encrypted=encrypt_value("sk-team", encryption_key),
    )
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.import_credentials_with_models_to_team(
        credential_ids=[team_cred.id],
        tenant_id=target_team.id,
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 0
    assert len(result.failed) == 1
    assert str(team_cred.id) in result.failed[0].credential_id


@pytest.mark.asyncio
async def test_import_credential_without_models(db_session, test_user: User) -> None:
    """凭据无关联模型 → 仅复制凭据，models_created 为空。"""
    target_team = await TeamService(db_session).create_team(
        name="import-no-models",
        slug=f"import-nm-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    cred = await _create_user_credential(db_session, test_user, name="no-models-cred")
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.import_credentials_with_models_to_team(
        credential_ids=[cred.id],
        tenant_id=target_team.id,
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 1
    assert len(result.succeeded[0].models_created) == 0


@pytest.mark.asyncio
async def test_import_partial_failure(db_session, test_user: User) -> None:
    """多条凭据部分成功部分失败。"""
    target_team = await TeamService(db_session).create_team(
        name="import-partial",
        slug=f"import-partial-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    good_cred = await _create_user_credential(db_session, test_user, name="good-cred")
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    bad_id = uuid.uuid4()  # non-existent
    result = await writes.import_credentials_with_models_to_team(
        credential_ids=[good_cred.id, bad_id],
        tenant_id=target_team.id,
        actor_user_id=test_user.id,
        is_platform_admin=False,
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 1
    assert result.succeeded[0].source_credential_id == good_cred.id
    assert len(result.failed) == 1


@pytest.mark.asyncio
async def test_import_permission_denied_for_non_owner(
    db_session, test_user: User
) -> None:
    """非 owner 且非 platform admin → 拒绝。"""
    target_team = await TeamService(db_session).create_team(
        name="import-perm-team",
        slug=f"import-perm-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    # Create a second user
    other_user = User(
        email=f"other_{uuid.uuid4()}@example.com",
        hashed_password="hashed_password",
        name="Other User",
    )
    db_session.add(other_user)
    await db_session.flush()
    # Add other_user as member
    await TeamService(db_session).add_member(target_team.id, other_user.id, role="member")
    await db_session.commit()

    cred = await _create_user_credential(db_session, test_user, name="owner-cred")
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.import_credentials_with_models_to_team(
        credential_ids=[cred.id],
        tenant_id=target_team.id,
        actor_user_id=other_user.id,  # NOT the owner of the credential
        is_platform_admin=False,
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 0
    assert len(result.failed) == 1
    assert result.failed[0].reason == "credential not found"


@pytest.mark.asyncio
async def test_copy_team_credential_to_personal_with_models(
    db_session, test_user: User
) -> None:
    """团队凭据 + 模型复制到个人 BYOK。"""
    personal_team = await TeamService(db_session).ensure_personal_team(test_user.id)
    source_team = await TeamService(db_session).create_team(
        name="copy-source-team",
        slug=f"copy-src-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    team_cred = await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=source_team.id,
        provider="openai",
        name="team-copy-src",
        api_key_encrypted=encrypt_value("sk-team-copy", encryption_key),
        created_by_user_id=test_user.id,
    )
    await GatewayModelRepository(db_session).create(
        tenant_id=source_team.id,
        name="team-model-1",
        capability="chat",
        real_model="openai/gpt-4o",
        credential_id=team_cred.id,
        provider="openai",
    )
    await db_session.commit()

    from domains.gateway.domain.policies.credential_copy_policy import CredentialCopyScope

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_credentials_with_models(
        credential_ids=[team_cred.id],
        source=CredentialCopyScope(kind="team", team_id=source_team.id),
        destination=CredentialCopyScope(kind="personal"),
        actor_user_id=test_user.id,
        is_platform_admin=False,
        source_team_role="owner",
        destination_team_role=None,
    )

    assert len(result.succeeded) == 1
    user_creds = await ProviderCredentialRepository(db_session).list_for_user(test_user.id)
    assert any(c.name == "team-copy-src" for c in user_creds)
    personal_models = await GatewayModelRepository(db_session).list_tenant_owned(
        personal_team.id
    )
    assert any(m.name == "team-model-1" for m in personal_models)


@pytest.mark.asyncio
async def test_copy_team_credential_to_other_team(db_session, test_user: User) -> None:
    """团队 A → 团队 B 复制凭据。"""
    source_team = await TeamService(db_session).create_team(
        name="copy-a",
        slug=f"copy-a-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    target_team = await TeamService(db_session).create_team(
        name="copy-b",
        slug=f"copy-b-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    await db_session.commit()

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    team_cred = await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=source_team.id,
        provider="openai",
        name="cross-team-cred",
        api_key_encrypted=encrypt_value("sk-cross", encryption_key),
        created_by_user_id=test_user.id,
    )
    await db_session.commit()

    from domains.gateway.domain.policies.credential_copy_policy import CredentialCopyScope

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_credentials_with_models(
        credential_ids=[team_cred.id],
        source=CredentialCopyScope(kind="team", team_id=source_team.id),
        destination=CredentialCopyScope(kind="team", team_id=target_team.id),
        actor_user_id=test_user.id,
        is_platform_admin=False,
        source_team_role="owner",
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 1
    target_creds = await ProviderCredentialRepository(db_session).list_for_tenant(target_team.id)
    assert len(target_creds) == 1
    assert target_creds[0].name == "cross-team-cred"


@pytest.mark.asyncio
async def test_copy_other_member_team_credential_denied(
    db_session, test_user: User
) -> None:
    """他人创建的 team 凭据 → member 不可复制（404）。"""
    team = await TeamService(db_session).create_team(
        name="copy-perm-team",
        slug=f"copy-perm-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    other_user = User(
        email=f"other_copy_{uuid.uuid4()}@example.com",
        hashed_password="hashed_password",
        name="Other Copy User",
    )
    db_session.add(other_user)
    await db_session.flush()
    await TeamService(db_session).add_member(team.id, other_user.id, role="member")
    await db_session.commit()

    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    team_cred = await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=team.id,
        provider="openai",
        name="owner-only-cred",
        api_key_encrypted=encrypt_value("sk-owner-only", encryption_key),
        created_by_user_id=test_user.id,
    )
    await db_session.commit()

    from domains.gateway.domain.policies.credential_copy_policy import CredentialCopyScope

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_credentials_with_models(
        credential_ids=[team_cred.id],
        source=CredentialCopyScope(kind="team", team_id=team.id),
        destination=CredentialCopyScope(kind="personal"),
        actor_user_id=other_user.id,
        is_platform_admin=False,
        source_team_role="member",
        destination_team_role=None,
    )

    assert len(result.succeeded) == 0
    assert len(result.failed) == 1


@pytest.mark.asyncio
async def test_platform_admin_can_copy_other_user_byok(db_session, test_user: User) -> None:
    """平台 admin 可复制他人 personal 凭据到团队。"""
    from domains.gateway.domain.policies.credential_copy_policy import CredentialCopyScope

    admin_user = User(
        email=f"platform_admin_{uuid.uuid4()}@example.com",
        hashed_password="hashed_password",
        name="Platform Admin",
        role="admin",
    )
    db_session.add(admin_user)
    await db_session.flush()

    target_team = await TeamService(db_session).create_team(
        name="admin-copy-target",
        slug=f"admin-copy-{uuid.uuid4().hex[:8]}",
        owner_user_id=admin_user.id,
    )
    cred = await _create_user_credential(db_session, test_user, name="victim-byok")
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_credentials_with_models(
        credential_ids=[cred.id],
        source=CredentialCopyScope(kind="personal"),
        destination=CredentialCopyScope(kind="team", team_id=target_team.id),
        actor_user_id=admin_user.id,
        is_platform_admin=True,
        source_team_role=None,
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 1
    assert len(result.failed) == 0
    team_creds = await ProviderCredentialRepository(db_session).list_for_tenant(target_team.id)
    assert len(team_creds) == 1


@pytest.mark.asyncio
async def test_platform_admin_cannot_copy_other_user_team_credential(
    db_session, test_user: User
) -> None:
    """平台 admin 不能复制他人私有 team 凭据（无旁路）。"""
    from domains.gateway.domain.policies.credential_copy_policy import CredentialCopyScope

    admin_user = User(
        email=f"platform_admin2_{uuid.uuid4()}@example.com",
        hashed_password="hashed_password",
        name="Platform Admin 2",
        role="admin",
    )
    db_session.add(admin_user)
    await db_session.flush()

    source_team = await TeamService(db_session).create_team(
        name="admin-deny-source",
        slug=f"admin-deny-{uuid.uuid4().hex[:8]}",
        owner_user_id=test_user.id,
    )
    target_team = await TeamService(db_session).create_team(
        name="admin-deny-target",
        slug=f"admin-deny-t-{uuid.uuid4().hex[:8]}",
        owner_user_id=admin_user.id,
    )
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    team_cred = await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=source_team.id,
        provider="openai",
        name="owner-private-cred",
        api_key_encrypted=encrypt_value("sk-private", encryption_key),
        created_by_user_id=test_user.id,
    )
    await db_session.commit()

    writes = GatewayManagementWriteService(db_session)
    result = await writes.copy_credentials_with_models(
        credential_ids=[team_cred.id],
        source=CredentialCopyScope(kind="team", team_id=source_team.id),
        destination=CredentialCopyScope(kind="team", team_id=target_team.id),
        actor_user_id=admin_user.id,
        is_platform_admin=True,
        source_team_role="admin",
        destination_team_role="owner",
    )

    assert len(result.succeeded) == 0
    assert len(result.failed) == 1
    assert result.failed[0].reason == "credential not found"
