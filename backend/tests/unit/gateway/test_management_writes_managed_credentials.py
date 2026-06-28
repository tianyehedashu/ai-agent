"""GatewayManagementWriteService 管理凭据：system 权限、删除占用、团队归属。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.agent.infrastructure.models.agent import Agent  # noqa: F401
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.errors import (
    CredentialNotFoundError,
    SystemCredentialAdminRequiredError,
)
from domains.gateway.domain.credential.credential_model_cascade import was_credential_cascade_disabled
from domains.gateway.domain.provider.provider_api_base import get_default_api_base
from domains.gateway.domain.types import CREDENTIAL_CASCADE_DISABLED_TAG
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.gateway.presentation.http_error_map import problem_context_from_gateway_domain
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential


@pytest.mark.asyncio
async def test_create_team_credential_backfills_default_api_base(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    writes = GatewayManagementWriteService(db_session)
    row = await writes.create_team_credential(
        tenant_id=team.id,
        created_by_user_id=test_user.id,
        provider="zhipuai",
        name="zhipu-default-base",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        api_bases=None,
        profile_id=None,
        extra=None,
    )
    assert row.api_base is None
    assert row.effective_api_base_openai == get_default_api_base("zhipuai")


@pytest.mark.asyncio
async def test_create_system_credential_requires_platform_admin(db_session) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(SystemCredentialAdminRequiredError):
        await writes.create_system_credential(
            is_platform_admin=False,
            provider="openai",
            name="sys-test",
            api_key_encrypted=encrypt_value("sk-fake", encryption_key),
            api_base=None,
            api_bases=None,
            profile_id=None,
            extra=None,
        )


@pytest.mark.asyncio
async def test_update_system_credential_requires_platform_admin(db_session, test_user) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name="sys-cred-test",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    with pytest.raises(SystemCredentialAdminRequiredError):
        await writes.update_managed_credential(
            cred.id,
            tenant_id=team.id,
            actor_user_id=test_user.id,
            team_role="owner",
            is_platform_admin=False,
            api_key_encrypted=None,
            api_base=None,
            api_bases=None,
            profile_id=None,
            extra=None,
            is_active=None,
            name=None,
        )


@pytest.mark.asyncio
async def test_delete_managed_credential_cascades_linked_models(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    model_repo = GatewayModelRepository(db_session)
    cred = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="deepseek",
        name="del-cascade",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    model_name = f"vm-{uuid.uuid4().hex[:6]}"
    model = await model_repo.create(
        tenant_id=team.id,
        name=model_name,
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred.id,
        provider="deepseek",
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)
    await writes.delete_managed_credential(
        cred.id,
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
    )
    await db_session.flush()
    assert await cred_repo.get(cred.id) is None
    assert await model_repo.get(model.id) is None


@pytest.mark.asyncio
async def test_delete_user_credential_cascades_personal_models(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    model_repo = GatewayModelRepository(db_session)
    cred = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="deepseek",
        name="user-del-cascade",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    model = await model_repo.create(
        tenant_id=team.id,
        name=f"pm-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred.id,
        provider="deepseek",
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)
    await writes.delete_user_credential(cred.id, actor_user_id=test_user.id)
    await db_session.flush()
    assert await cred_repo.get(cred.id) is None
    assert await model_repo.get(model.id) is None


@pytest.mark.asyncio
async def test_delete_user_credential_purges_credential_and_model_grants(
    db_session, test_user
) -> None:
    ts = TeamService(db_session)
    team = await ts.ensure_personal_team(test_user.id)
    shared = await ts.create_team(name="Grant Purge Team", owner_user_id=test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    model_repo = GatewayModelRepository(db_session)
    cred = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="deepseek",
        name="user-grant-purge",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    model = await model_repo.create(
        tenant_id=team.id,
        name=f"pm-grant-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred.id,
        provider="deepseek",
    )
    from domains.gateway.infrastructure.repositories.resource_grant_repository import (
        GatewayResourceGrantRepository,
    )

    grant_repo = GatewayResourceGrantRepository(db_session)
    await grant_repo.create(
        owner_user_id=test_user.id,
        subject_kind="credential",
        subject_id=cred.id,
        target_team_id=shared.id,
        granted_by=test_user.id,
    )
    await grant_repo.create(
        owner_user_id=test_user.id,
        subject_kind="model",
        subject_id=model.id,
        target_team_id=shared.id,
        granted_by=test_user.id,
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    await writes.delete_user_credential(cred.id, actor_user_id=test_user.id)
    await db_session.flush()

    assert await grant_repo.list_for_subject("credential", cred.id) == []
    assert await grant_repo.list_for_subject("model", model.id) == []


@pytest.mark.asyncio
async def test_update_managed_wrong_team_returns_not_found(db_session, test_user) -> None:
    team_a = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(db_session, team_a.id, name="other-team-cred")
    await db_session.flush()
    fake_team = uuid.uuid4()
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(CredentialNotFoundError):
        await writes.update_managed_credential(
            cred.id,
            tenant_id=fake_team,
            actor_user_id=test_user.id,
            team_role="owner",
            is_platform_admin=False,
            api_key_encrypted=None,
            api_base=None,
            api_bases=None,
            profile_id=None,
            extra=None,
            is_active=True,
            name="x",
        )


def test_system_credential_admin_error_maps_to_403() -> None:
    ctx = problem_context_from_gateway_domain(SystemCredentialAdminRequiredError())
    assert ctx.status_code == 403
    assert "平台管理员" in str(ctx.detail)


@pytest.mark.asyncio
async def test_deactivate_managed_credential_cascades_model_enabled(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    model_repo = GatewayModelRepository(db_session)
    cred = await cred_repo.create_for_tenant(
        tenant_id=team.id,
        provider="deepseek",
        name="inactive-cascade",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        created_by_user_id=test_user.id,
    )
    model = await model_repo.create(
        tenant_id=team.id,
        name=f"vm-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred.id,
        provider="deepseek",
        enabled=True,
    )
    manual_off = await model_repo.create(
        tenant_id=team.id,
        name=f"vm-off-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred.id,
        provider="deepseek",
        enabled=False,
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)
    await writes.update_managed_credential(
        cred.id,
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
        api_key_encrypted=None,
        api_base=None,
        api_bases=None,
        profile_id=None,
        extra=None,
        is_active=False,
        name=None,
    )
    await db_session.flush()
    refreshed = await model_repo.get(model.id)
    manual_refreshed = await model_repo.get(manual_off.id)
    assert refreshed is not None and refreshed.enabled is False
    assert refreshed.tags is not None
    assert refreshed.tags.get(CREDENTIAL_CASCADE_DISABLED_TAG) is True
    assert was_credential_cascade_disabled(refreshed.tags)
    assert manual_refreshed is not None and manual_refreshed.enabled is False
    assert not was_credential_cascade_disabled(manual_refreshed.tags)

    await writes.update_managed_credential(
        cred.id,
        tenant_id=team.id,
        actor_user_id=test_user.id,
        team_role="owner",
        is_platform_admin=False,
        api_key_encrypted=None,
        api_base=None,
        api_bases=None,
        profile_id=None,
        extra=None,
        is_active=True,
        name=None,
    )
    await db_session.flush()
    restored = await model_repo.get(model.id)
    still_off = await model_repo.get(manual_off.id)
    assert restored is not None and restored.enabled is True
    assert CREDENTIAL_CASCADE_DISABLED_TAG not in (restored.tags or {})
    assert not was_credential_cascade_disabled(restored.tags)
    assert still_off is not None and still_off.enabled is False


@pytest.mark.asyncio
async def test_update_config_managed_system_credential_rejects_rename(
    db_session, test_user
) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name="app-config-default",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        extra={"managed_by": "config"},
    )
    await db_session.flush()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError, match="不可重命名"):
        await writes.update_managed_credential(
            cred.id,
            tenant_id=team.id,
            actor_user_id=test_user.id,
            team_role="owner",
            is_platform_admin=True,
            api_key_encrypted=None,
            api_base=None,
            api_bases=None,
            profile_id=None,
            extra=None,
            is_active=None,
            name="new-name",
        )
