"""团队 GatewayModel 创建：凭据与 provider 一致性。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError


@pytest.mark.asyncio
async def test_create_gateway_model_rejects_cred_provider_mismatch(
    db_session,
    test_user: User,
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team.id,
        provider="openai",
        name="mismatch-cred",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ValidationError, match="凭据提供商"):
        await writes.create_gateway_model(
            team_id=team.id,
            name=f"m-{uuid.uuid4().hex[:6]}",
            capability="chat",
            real_model="gpt-4o-mini",
            credential_id=cred.id,
            provider="dashscope",
            weight=1,
            rpm_limit=None,
            tpm_limit=None,
            tags=None,
            is_platform_admin=False,
        )
