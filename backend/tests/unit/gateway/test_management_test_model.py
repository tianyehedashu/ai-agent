"""GatewayManagementWriteService.test_gateway_model capability 分支与持久化"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.gateway.application.management.writes import GatewayManagementWriteService
from domains.gateway.domain.errors import ManagementEntityNotFoundError
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from tests.unit.gateway.credential_test_helpers import create_tenant_test_credential, team_owner_actor_kw


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
    cred = await create_tenant_test_credential(
        db_session, team.id, provider=provider, name=f"{provider}-test"
    )
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
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
        {"choices": [type("C", (), {"message": type("M", (), {"content": "Hello!"})()})()]},
    )()
    writes = GatewayManagementWriteService(db_session)

    # acompletion 在 test_gateway_model 内部延迟导入，patch litellm 模块入口即可。
    with patch("litellm.acompletion", new=AsyncMock(return_value=fake)):
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

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
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

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
async def test_dashscope_embedding_probe_uses_compatible_client(db_session, test_user) -> None:
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="embedding",
        real_model="text-embedding-v3",
        provider="dashscope",
    )
    writes = GatewayManagementWriteService(db_session)
    fake_response = {
        "object": "list",
        "data": [],
        "model": "text-embedding-v3",
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }

    with (
        patch(
            "domains.gateway.application.management.write_modules.probe.perform_dashscope_embedding",
            new=AsyncMock(return_value=fake_response),
        ) as perform_mock,
        patch("litellm.aembedding", new=AsyncMock()) as litellm_embed,
    ):
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is True
    perform_mock.assert_awaited_once()
    litellm_embed.assert_not_awaited()


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
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is True
    assert result["status"] == "success"
    mock_embed.assert_awaited_once()
    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "success"
    assert refreshed.last_test_reason is None


@pytest.mark.asyncio
async def test_image_capability_uses_aimage_generation(db_session, test_user) -> None:
    """非火山 provider 的 image 模型仍走 LiteLLM ``aimage_generation``。"""
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="image",
        real_model="dall-e-3",
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)
    fake_img = type(
        "ImgResp",
        (),
        {
            "data": [
                type("D", (), {"url": "https://example.com/x.png", "b64_json": None})(),
            ]
        },
    )()

    with patch("litellm.aimage_generation", new=AsyncMock(return_value=fake_img)) as mock_img:
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is True
    assert result["status"] == "success"
    assert result.get("response_preview")
    mock_img.assert_awaited_once()
    call_kw = mock_img.await_args.kwargs
    assert call_kw["size"] == "1024x1024"
    assert call_kw["n"] == 1
    assert call_kw["prompt"] == "ping"
    assert call_kw["timeout"] == 60

    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "success"
    assert refreshed.last_test_reason is None


@pytest.mark.asyncio
async def test_image_capability_failure_persists(db_session, test_user) -> None:
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="image",
        real_model="dall-e-3",
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)

    with patch(
        "litellm.aimage_generation",
        new=AsyncMock(side_effect=RuntimeError("502 Bad Gateway")),
    ):
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is False
    assert result["status"] == "failed"
    assert "502" in result["message"]

    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "failed"
    assert refreshed.last_test_reason
    assert "502" in refreshed.last_test_reason


@pytest.mark.asyncio
async def test_video_generation_capability_uses_avideo_generation(db_session, test_user) -> None:
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="video_generation",
        real_model="sora-2",
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)
    fake_video = type(
        "VideoResp",
        (),
        {"id": "video_abc123", "status": "queued"},
    )()

    with patch("litellm.avideo_generation", new=AsyncMock(return_value=fake_video)) as mock_video:
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is True
    assert result["status"] == "success"
    assert result.get("response_preview") == "queued: video_abc123"
    mock_video.assert_awaited_once()
    call_kw = mock_video.await_args.kwargs
    assert call_kw["prompt"] == "ping"
    assert call_kw["seconds"] == "5"
    assert call_kw["timeout"] == 120

    refreshed = await GatewayModelRepository(db_session).get(model_id)
    assert refreshed is not None
    assert refreshed.last_test_status == "success"
    assert refreshed.last_test_reason is None


@pytest.mark.asyncio
async def test_unsupported_capability_returns_failed(db_session, test_user) -> None:
    """非 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES`` 仍写回 failed，避免 UI 留'未测过'。"""
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="moderation",
        real_model="text-moderation-latest",
        provider="openai",
    )
    writes = GatewayManagementWriteService(db_session)

    result = await writes.test_gateway_model(
        model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
    )

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
        await writes.test_gateway_model(
            uuid.uuid4(), tenant_id=team.id, **team_owner_actor_kw(test_user)
        )


@pytest.mark.asyncio
async def test_volcengine_image_probe_uses_image_endpoint_from_extra(db_session, test_user) -> None:
    """火山生图模型探活：走自定义 HTTP，不再用 LiteLLM ``aimage_generation``。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session,
        team.id,
        provider="volcengine",
        name="volc-image",
        extra={"image_endpoint_id": "ep-image-test"},
    )
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=f"vmodel-{uuid.uuid4().hex[:6]}",
        capability="image",
        real_model="volcengine/seedream",
        credential_id=cred.id,
        provider="volcengine",
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)

    captured: dict[str, str] = {}

    async def fake_perform(request, *, timeout=60.0):
        captured["model"] = request.json_body["model"]
        captured["url"] = request.url
        return {"data": [{"url": "https://cdn.example.com/img.png"}]}

    with patch(
        "domains.gateway.application.management.write_modules.probe.perform_volcengine_image_generation",
        new=fake_perform,
    ):
        result = await writes.test_gateway_model(
            model.id, tenant_id=team.id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is True
    assert captured["model"] == "ep-image-test"
    assert captured["url"].endswith("/images/generations")


@pytest.mark.asyncio
async def test_volcengine_image_probe_fails_when_endpoint_missing(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    cred = await create_tenant_test_credential(
        db_session,
        team.id,
        provider="volcengine",
        name="volc-image-no-ep",
    )
    model = await GatewayModelRepository(db_session).create(
        tenant_id=team.id,
        name=f"vmodel-{uuid.uuid4().hex[:6]}",
        capability="image",
        real_model="volcengine/seedream",
        credential_id=cred.id,
        provider="volcengine",
    )
    await db_session.flush()
    writes = GatewayManagementWriteService(db_session)

    result = await writes.test_gateway_model(
        model.id, tenant_id=team.id, **team_owner_actor_kw(test_user)
    )
    assert result["success"] is False
    assert "image_endpoint_id" in result["reason"]


@pytest.mark.asyncio
async def test_volcengine_video_probe_uses_direct_task_api(db_session, test_user) -> None:
    """火山 Seedance 视频探活：走方舟 ``/contents/generations/tasks``，不用 LiteLLM。"""
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="video_generation",
        real_model="doubao-seedance-1-0-lite-t2v-250428",
        provider="volcengine",
    )
    writes = GatewayManagementWriteService(db_session)
    captured: dict[str, str] = {}

    async def fake_perform(request, *, timeout=120.0):
        captured["model"] = request.json_body["model"]
        captured["url"] = request.url
        return {"id": "cgt-test", "status": "queued"}

    with (
        patch(
            "domains.gateway.application.management.write_modules.probe.perform_volcengine_video_create",
            new=fake_perform,
        ),
        patch("litellm.avideo_generation", new=AsyncMock()) as mock_video,
    ):
        result = await writes.test_gateway_model(
            model_id, tenant_id=team_id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is True
    assert result.get("response_preview") == "queued: cgt-test"
    assert captured["model"] == "doubao-seedance-1-0-lite-t2v-250428"
    assert captured["url"].endswith("/contents/generations/tasks")
    mock_video.assert_not_called()


@pytest.mark.asyncio
async def test_system_model_from_merged_list_can_be_probed(db_session, test_user) -> None:
    """``list_for_tenant`` 合并的系统模型 id 应能走 test_gateway_model（写 system_gateway_models）。"""
    from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog

    await sync_app_config_gateway_catalog(db_session)
    await db_session.flush()
    repo = GatewayModelRepository(db_session)
    system_rows = await repo.list_system(only_enabled=True, capability="chat")
    if not system_rows:
        pytest.skip("catalog sync produced no chat system models")
    system_model = system_rows[0]
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    writes = GatewayManagementWriteService(db_session)

    fake = type(
        "Resp",
        (),
        {"choices": [type("C", (), {"message": type("M", (), {"content": "pong"})()})()]},
    )()
    with patch("litellm.acompletion", new=AsyncMock(return_value=fake)):
        result = await writes.test_gateway_model(
            system_model.id, tenant_id=team.id, **team_owner_actor_kw(test_user)
        )

    assert result["success"] is True
    refreshed = await repo.get_system(system_model.id)
    assert refreshed is not None
    assert refreshed.last_test_status == "success"
    assert refreshed.last_tested_at is not None
