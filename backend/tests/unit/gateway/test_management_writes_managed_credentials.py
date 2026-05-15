"""GatewayManagementWriteService 管理凭据：system 权限、删除占用、团队归属。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.agent.infrastructure.models.agent import Agent  # noqa: F401
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.errors import (
    CredentialInUseError,
    CredentialNotFoundError,
    SystemCredentialAdminRequiredError,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


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
            extra=None,
        )


@pytest.mark.asyncio
async def test_update_system_credential_requires_platform_admin(db_session, test_user) -> None:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="system",
        scope_id=None,
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
            team_id=team.id,
            is_platform_admin=False,
            api_key_encrypted=None,
            api_base=None,
            extra=None,
            is_active=None,
            name=None,
        )


@pytest.mark.asyncio
async def test_delete_managed_credential_raises_in_use(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team.id,
        provider="deepseek",
        name="del-in-use",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=f"vm-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="deepseek/deepseek-chat",
        credential_id=cred.id,
        provider="deepseek",
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(CredentialInUseError):
        await writes.delete_managed_credential(
            cred.id,
            team_id=team.id,
            is_platform_admin=False,
        )


@pytest.mark.asyncio
async def test_update_managed_wrong_team_returns_not_found(db_session, test_user) -> None:
    team_a = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team_a.id,
        provider="openai",
        name="other-team-cred",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    fake_team = uuid.uuid4()
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(CredentialNotFoundError):
        await writes.update_managed_credential(
            cred.id,
            team_id=fake_team,
            is_platform_admin=False,
            api_key_encrypted=None,
            api_base=None,
            extra=None,
            is_active=True,
            name="x",
        )


def test_system_credential_admin_error_maps_to_403() -> None:
    exc = http_exception_from_gateway_domain(SystemCredentialAdminRequiredError())
    assert exc.status_code == 403
    assert "平台管理员" in str(exc.detail)
