"""delete_personal_model / batch 删除时清理 resource grant。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.gateway.infrastructure.repositories.resource_grant_repository import (
    GatewayResourceGrantRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


@pytest.mark.asyncio
async def test_delete_personal_model_purges_model_grants(db_session, test_user) -> None:
    ts = TeamService(db_session)
    personal = await ts.ensure_personal_team(test_user.id)
    shared = await ts.create_team(name="Model Grant Purge Team", owner_user_id=test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred_repo = ProviderCredentialRepository(db_session)
    model_repo = GatewayModelRepository(db_session)
    cred = await cred_repo.create(
        scope="user",
        scope_id=test_user.id,
        provider="openai",
        name="model-grant-purge-cred",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
    )
    model = await model_repo.create(
        tenant_id=personal.id,
        name=f"pm-purge-{uuid.uuid4().hex[:6]}",
        capability="chat",
        real_model="openai/gpt-4o-mini",
        credential_id=cred.id,
        provider="openai",
    )
    grant_repo = GatewayResourceGrantRepository(db_session)
    await grant_repo.create(
        owner_user_id=test_user.id,
        subject_kind="model",
        subject_id=model.id,
        target_team_id=shared.id,
        granted_by=test_user.id,
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    await writes.delete_personal_model(test_user.id, model.id)
    await db_session.flush()

    assert await model_repo.get(model.id) is None
    assert await grant_repo.list_for_subject("model", model.id) == []
