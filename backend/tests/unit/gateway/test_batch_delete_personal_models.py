"""delete_personal_models_batch：个人 tenant 批量删除。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError


@pytest.mark.asyncio
async def test_delete_personal_models_batch_success(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        tenant_id=team.id,
        provider="openai",
        name=f"personal-batch-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        scope="user",
        scope_id=test_user.id,
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    rows = await writes.create_personal_models(
        test_user.id,
        display_name="Batch Del",
        provider="openai",
        model_id="gpt-4o-mini",
        credential_id=cred.id,
        model_types=["text"],
        tags=None,
    )
    await db_session.flush()
    model_id = rows[0].id

    result = await writes.delete_personal_models_batch(test_user.id, [model_id])
    await db_session.flush()

    assert result.succeeded == [model_id]
    assert result.failed == []
    assert await GatewayModelRepository(db_session).get_for_tenant(model_id, team.id) is None


@pytest.mark.asyncio
async def test_delete_personal_models_batch_unknown_id_fails(db_session, test_user) -> None:
    writes = GatewayManagementWriteService(db_session)
    unknown_id = uuid.uuid4()
    result = await writes.delete_personal_models_batch(test_user.id, [unknown_id])
    assert result.succeeded == []
    assert len(result.failed) == 1
    assert result.failed[0].id == unknown_id


@pytest.mark.asyncio
async def test_delete_personal_models_batch_rejects_over_limit(db_session, test_user) -> None:
    writes = GatewayManagementWriteService(db_session)
    too_many = [uuid.uuid4() for _ in range(201)]
    with pytest.raises(ValidationError):
        await writes.delete_personal_models_batch(test_user.id, too_many)
