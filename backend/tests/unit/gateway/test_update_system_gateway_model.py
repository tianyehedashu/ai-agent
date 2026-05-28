"""update_gateway_model：系统模型行需平台管理员。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.errors import SystemCredentialAdminRequiredError
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


@pytest.mark.asyncio
async def test_update_system_gateway_model_requires_platform_admin(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await SystemProviderCredentialRepository(db_session).create(
        provider="openai",
        name=f"sys-upd-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()
    model = SystemGatewayModel(
        name=f"sys-upd-model-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
        enabled=True,
    )
    db_session.add(model)
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(SystemCredentialAdminRequiredError):
        await writes.update_gateway_model(
            model.id,
            tenant_id=team.id,
            is_platform_admin=False,
            fields={"enabled": False},
        )

    updated = await writes.update_gateway_model(
        model.id,
        tenant_id=team.id,
        is_platform_admin=True,
        fields={"enabled": False},
    )
    assert updated.enabled is False
    reloaded = await GatewayModelRepository(db_session).get_system(model.id)
    assert reloaded is not None
    assert reloaded.enabled is False
