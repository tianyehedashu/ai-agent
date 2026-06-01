"""update_personal_model 能力编辑单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock
import uuid

import pytest

from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.litellm_capability_mapping import LitellmModelInfoHints
from domains.gateway.infrastructure.litellm_capability_hint_adapter import (
    LitellmCapabilityHintAdapter,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.exceptions import ValidationError


async def _seed_personal_model(
    db_session,
    test_user,
    *,
    capability: str = "chat",
    real_model: str = "volcengine/kimi-k2.6",
    provider: str = "volcengine",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred_id = uuid.uuid4()
    repo = GatewayModelRepository(db_session)
    row = await repo.create(
        tenant_id=team.id,
        name=f"my-kimi-{uuid.uuid4().hex[:6]}",
        capability=capability,
        real_model=real_model,
        credential_id=cred_id,
        provider=provider,
        tags={"display_name": "Kimi"},
    )
    await db_session.flush()
    user_id = test_user.id if isinstance(test_user.id, uuid.UUID) else uuid.UUID(str(test_user.id))
    return team.id, row.id, user_id


@pytest.mark.asyncio
async def test_update_personal_model_rejects_multiple_model_types(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    writes = GatewayManagementWriteService(db_session)

    monkeypatch.setattr(
        writes,
        "_assert_user_owns_credential",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))

    with pytest.raises(ValidationError, match="单一 model_type"):
        await writes.update_personal_model(
            user_uuid,
            model_id,
            fields={"model_types": ["text", "image"]},
        )


@pytest.mark.asyncio
async def test_update_personal_model_image_type_sets_vision_tag(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_id, model_id, user_uuid = await _seed_personal_model(db_session, test_user)
    writes = GatewayManagementWriteService(db_session)

    def _vision_hints(_self, *, provider: str, real_model: str) -> LitellmModelInfoHints:
        _ = provider, real_model
        return LitellmModelInfoHints(supports_vision=True)

    monkeypatch.setattr(
        writes,
        "_assert_user_owns_credential",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        writes,
        "_ensure_personal_tenant_id",
        AsyncMock(return_value=tenant_id),
    )
    monkeypatch.setattr(writes, "reload_litellm_router", AsyncMock(return_value=None))
    monkeypatch.setattr(LitellmCapabilityHintAdapter, "get_model_hints", _vision_hints)

    updated = await writes.update_personal_model(
        user_uuid,
        model_id,
        fields={"model_types": ["image"]},
    )
    assert updated.tags is not None
    assert updated.tags.get("supports_vision") is True

    repo = GatewayModelRepository(db_session)
    reloaded = await repo.get_for_tenant(model_id, tenant_id)
    assert reloaded is not None
    assert reloaded.tags.get("supports_vision") is True
