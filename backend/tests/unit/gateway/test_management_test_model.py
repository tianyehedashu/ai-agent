"""GatewayManagementWriteService.test_gateway_model 三条 capability 分支与持久化"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.errors import ManagementEntityNotFoundError
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.crypto import derive_encryption_key, encrypt_value


async def _seed_team_credential_and_model(
    db_session,
    test_user,
    *,
    capability: str,
    real_model: str = "deepseek/deepseek-chat",
    provider: str = "deepseek",
) -> tuple[uuid.UUID, uuid.UUID]:
    """建一条团队凭据 + 一条团队模型，返回 (team_id, model_id)。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    cred = await ProviderCredentialRepository(db_session).create(
        scope="team",
        scope_id=team.id,
        provider=provider,
        name=f"{provider}-test",
        api_key_encrypted=encrypt_value("sk-fake-test-key", encryption_key),
        api_base=None,
    )
    model = await GatewayModelRepository(db_session).create(
        team_id=team.id,
        name=f"vmodel-{uuid.uuid4().hex[:6]}",
        capability=capability,
        real_model=real_model,
        credential_id=cred.id,
        provider=provider,
    )
    await db_session.flush()
    return team.id, model.id


@pytest.mark.asyncio
async def test_chat_capability_success_persists(db_session, test_user) -> None:
    team_id, model_id = await _seed_team_credential_and_model(
        db_session, test_user, capability="chat"
    )
    fake = type(
        "Resp",
        (),
        {
            "choices": [
                type(
                    "C", (), {"message": type("M", (), {"content": "Hello!"})()}
                )()
            ]
        },
    )()
    writes = GatewayManagementWriteService(db_session)

    # acompletion 在 test_gateway_model 内部延迟导入，patch litellm 模块入口即可。
    with patch("litellm.acompletion", new=AsyncMock(return_value=fake)):
        result = await writes.test_gateway_model(model_id, team_id=team_id)

    assert result["success"] is True
    assert result["status"] == "success"
    assert "tested_at" in result

    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "success"
    assert refreshed.last_tested_at is not None
    assert refreshed.last_test_reason is None


@pytest.mark.asyncio
async def test_chat_capability_failure_persists(db_session, test_user) -> None:
    team_id, model_id = await _seed_team_credential_and_model(
        db_session, test_user, capability="chat"
    )
    writes = GatewayManagementWriteService(db_session)

    with patch(
        "litellm.acompletion",
        new=AsyncMock(side_effect=RuntimeError("401 Unauthorized")),
    ):
        result = await writes.test_gateway_model(model_id, team_id=team_id)

    assert result["success"] is False
    assert result["status"] == "failed"
    assert "401" in result["message"]

    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "failed"
    assert refreshed.last_tested_at is not None
    assert refreshed.last_test_reason
    assert "401" in refreshed.last_test_reason


@pytest.mark.asyncio
async def test_embedding_capability_uses_aembedding(db_session, test_user) -> None:
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="embedding",
        real_model="openai/text-embedding-3-small",
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)

    with patch("litellm.aembedding", new=AsyncMock(return_value={"data": []})) as mock_embed:
        result = await writes.test_gateway_model(model_id, team_id=team_id)

    assert result["success"] is True
    assert result["status"] == "success"
    mock_embed.assert_awaited_once()
    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "success"
    assert refreshed.last_test_reason is None


@pytest.mark.asyncio
async def test_unsupported_capability_returns_failed(db_session, test_user) -> None:
    """capability=image 暂不做真实探测，写回 failed 让 UI 不留'未测过'。"""
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="image",
        real_model="dall-e-3",
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)

    result = await writes.test_gateway_model(model_id, team_id=team_id)

    assert result["success"] is False
    assert result["status"] == "failed"
    assert "暂不支持" in result["message"]
    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "failed"
    assert refreshed.last_test_reason
    assert "暂不支持" in refreshed.last_test_reason


@pytest.mark.asyncio
async def test_unknown_model_raises(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)
    with pytest.raises(ManagementEntityNotFoundError):
        await writes.test_gateway_model(uuid.uuid4(), team_id=team.id)
