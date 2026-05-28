"""resync_personal_models_capabilities_batch：个人 tenant 批量同步能力。"""

from __future__ import annotations

from unittest.mock import AsyncMock
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
from domains.gateway.infrastructure.litellm_capability_hint_adapter import (
    LitellmCapabilityHintAdapter,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value
from libs.exceptions import ValidationError


@pytest.mark.asyncio
async def test_resync_personal_models_capabilities_batch_success(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        tenant_id=team.id,
        provider="openai",
        name=f"personal-resync-cred-{uuid.uuid4().hex[:6]}",
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=None,
        scope="user",
        scope_id=test_user.id,
    )
    await db_session.flush()

    writes = GatewayManagementWriteService(db_session)
    rows = await writes.create_personal_models(
        test_user.id,
        display_name="Resync OK",
        provider="openai",
        model_id="gpt-4o-mini",
        credential_id=cred.id,
        model_types=["text"],
        tags=None,
    )
    await db_session.flush()
    model_id = rows[0].id

    def _vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
        _ = provider, real_model
        return LitellmModelInfoHints(supports_vision=True)

    monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _vision_hints)
    monkeypatch.setattr(
        writes,
        "reload_litellm_router",
        AsyncMock(),
    )

    result = await writes.resync_personal_models_capabilities_batch(
        test_user.id, [model_id]
    )

    assert result.succeeded == [model_id]
    assert result.failed == []


@pytest.mark.asyncio
async def test_resync_personal_models_capabilities_batch_unknown_id_fails(
    db_session, test_user
) -> None:
    writes = GatewayManagementWriteService(db_session)
    unknown_id = uuid.uuid4()
    result = await writes.resync_personal_models_capabilities_batch(
        test_user.id, [unknown_id]
    )
    assert result.succeeded == []
    assert len(result.failed) == 1
    assert result.failed[0].id == unknown_id


@pytest.mark.asyncio
async def test_resync_personal_models_capabilities_batch_rejects_over_limit(
    db_session, test_user
) -> None:
    writes = GatewayManagementWriteService(db_session)
    too_many = [uuid.uuid4() for _ in range(201)]
    with pytest.raises(ValidationError):
        await writes.resync_personal_models_capabilities_batch(test_user.id, too_many)
