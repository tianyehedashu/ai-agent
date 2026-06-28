"""
OpenAI 兼容入口 /api/v1/openai/v1/* 集成测试（虚拟 Key + dev_client）。
"""

from __future__ import annotations

import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.proxy.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.application.proxy.proxy_timing import (
    HEADER_GATEWAY_PREFLIGHT_MS,
    HEADER_GATEWAY_UPSTREAM_MS,
)
from domains.gateway.infrastructure.litellm.router_singleton import reload_router
from domains.identity.domain.api_key_types import ApiKeyScope
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.api.paths import openai_compat_base
from libs.iam.permission_context import clear_permission_context

_OPENAI_MODELS = f"{openai_compat_base()}/models"
_OPENAI_CHAT = f"{openai_compat_base()}/chat/completions"
_API_KEYS = "/api/v1/api-keys/"


def _fake_chat_completion(*, stream: bool = False) -> Any:
    message = types.SimpleNamespace(content="ok", tool_calls=None, reasoning_content=None)
    choice = types.SimpleNamespace(message=message, finish_reason="stop", delta=None)
    usage = types.SimpleNamespace(
        prompt_tokens=3,
        completion_tokens=2,
        total_tokens=5,
        prompt_tokens_details={},
        completion_tokens_details={},
    )
    if stream:

        async def _gen():
            delta_choice = types.SimpleNamespace(
                delta=types.SimpleNamespace(content="ok", reasoning_content=None),
                finish_reason=None,
            )
            yield types.SimpleNamespace(choices=[delta_choice], usage=None, id="chatcmpl-stream")
            stop_choice = types.SimpleNamespace(
                delta=types.SimpleNamespace(content="", reasoning_content=None),
                finish_reason="stop",
            )
            yield types.SimpleNamespace(
                choices=[stop_choice],
                usage=usage,
                id="chatcmpl-stream",
            )

        return _gen()

    return types.SimpleNamespace(
        id="chatcmpl-test",
        choices=[choice],
        usage=usage,
        model="gpt-4o-mini",
    )


async def _setup_team_model_vkey(
    dev_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
    test_user: User,
) -> tuple[str, str]:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    team_id = team.id
    await db_session.commit()
    cred = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/credentials",
        headers=auth_headers,
        json={
            "provider": "openai",
            "name": f"timing-cred-{uuid.uuid4().hex[:8]}",
            "api_key": "sk-timing-int-test-key-123456789",
            "scope": "team",
        },
    )
    assert cred.status_code == 201, cred.text
    cid = cred.json()["id"]
    model_name = f"timing-{uuid.uuid4().hex[:6]}"
    model = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/models",
        headers=auth_headers,
        json={
            "name": model_name,
            "capability": "chat",
            "real_model": "gpt-4o-mini",
            "credential_id": cid,
            "provider": "openai",
        },
    )
    assert model.status_code == 201, model.text
    await reload_router(db_session)
    key = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/keys",
        headers=auth_headers,
        json={"name": f"timing-vkey-{uuid.uuid4().hex[:8]}"},
    )
    assert key.status_code == 201, key.text
    return model_name, key.json()["plain_key"]


@pytest.mark.integration
class TestOpenAiCompatApi:
    @pytest.mark.asyncio
    async def test_v1_models_requires_bearer(self, dev_client: AsyncClient) -> None:
        r = await dev_client.get(_OPENAI_MODELS)
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_v1_models_returns_openai_list_shape(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        try:
            team = await TeamService(db_session).ensure_personal_team(test_user.id)
            await db_session.commit()

            mgmt_headers = auth_headers
            ck = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/keys",
                headers=mgmt_headers,
                json={"name": "itest-openai-compat-models"},
            )
            assert ck.status_code == 201, ck.text
            plain_key = ck.json()["plain_key"]

            r = await dev_client.get(
                _OPENAI_MODELS,
                headers={"Authorization": f"Bearer {plain_key}"},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("object") == "list"
            data = body.get("data")
            assert isinstance(data, list)
            if data:
                first = data[0]
                assert "model_types" in first
                assert isinstance(first["model_types"], list)
                gateway = first.get("gateway")
                assert isinstance(gateway, dict)
                assert "callable" in gateway
                assert "connectivity_status" in gateway
                assert "entitlement_status" in gateway
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_platform_api_key_gateway_proxy_requires_team_grant(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """平台 sk-* 的 gateway:proxy 只能访问 grant 授权的团队。"""
        try:
            teams = TeamService(db_session)
            personal = await teams.ensure_personal_team(test_user.id)
            shared = await teams.create_team(
                name="Shared API Key Grant Team",
                owner_user_id=test_user.id,
            )
            await db_session.commit()

            created = await dev_client.post(
                _API_KEYS,
                headers=auth_headers,
                json={
                    "name": "platform-gateway-default-personal",
                    "scopes": [ApiKeyScope.GATEWAY_PROXY.value],
                    "expires_in_days": 30,
                },
            )
            assert created.status_code == 201, created.text
            plain_key = created.json()["plain_key"]
            grants = created.json()["api_key"]["gateway_grants"]
            assert [g["team_id"] for g in grants] == [str(personal.id)]

            personal_models = await dev_client.get(
                _OPENAI_MODELS,
                headers={"Authorization": f"Bearer {plain_key}"},
            )
            assert personal_models.status_code == 200, personal_models.text

            shared_denied = await dev_client.get(
                _OPENAI_MODELS,
                headers={
                    "Authorization": f"Bearer {plain_key}",
                    "X-Team-Id": str(shared.id),
                },
            )
            assert shared_denied.status_code == 403, shared_denied.text

            bad_team_header = await dev_client.get(
                _OPENAI_MODELS,
                headers={
                    "Authorization": f"Bearer {plain_key}",
                    "X-Team-Id": "not-a-uuid",
                },
            )
            assert bad_team_header.status_code == 400, bad_team_header.text
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_platform_api_key_explicit_gateway_grant_allows_selected_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        try:
            shared = await TeamService(db_session).create_team(
                name="Explicit API Key Grant Team",
                owner_user_id=test_user.id,
            )
            await db_session.commit()

            created = await dev_client.post(
                _API_KEYS,
                headers=auth_headers,
                json={
                    "name": "platform-gateway-shared",
                    "scopes": [ApiKeyScope.GATEWAY_PROXY.value],
                    "expires_in_days": 30,
                    "gateway_grants": [
                        {
                            "team_id": str(shared.id),
                            "allowed_capabilities": ["chat"],
                            "rpm_limit": 10,
                        }
                    ],
                },
            )
            assert created.status_code == 201, created.text
            body = created.json()
            assert body["api_key"]["gateway_grants"][0]["team_id"] == str(shared.id)
            assert body["api_key"]["gateway_grants"][0]["allowed_capabilities"] == ["chat"]
            plain_key = body["plain_key"]

            selected = await dev_client.get(
                _OPENAI_MODELS,
                headers={
                    "Authorization": f"Bearer {plain_key}",
                    "X-Team-Id": str(shared.id),
                },
            )
            assert selected.status_code == 200, selected.text
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_platform_api_key_proxy_records_identity_usage(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """平台 sk-* 调用 /v1/* 后应回写 Identity usage_count。"""
        try:
            await TeamService(db_session).ensure_personal_team(test_user.id)
            await db_session.commit()

            created = await dev_client.post(
                _API_KEYS,
                headers=auth_headers,
                json={
                    "name": "platform-gateway-usage-log",
                    "scopes": [ApiKeyScope.GATEWAY_PROXY.value],
                    "expires_in_days": 30,
                },
            )
            assert created.status_code == 201, created.text
            body = created.json()
            api_key_id = body["api_key"]["id"]
            plain_key = body["plain_key"]
            assert body["api_key"]["usage_count"] == 0

            listed = await dev_client.get(
                _OPENAI_MODELS,
                headers={"Authorization": f"Bearer {plain_key}"},
            )
            assert listed.status_code == 200, listed.text

            detail = await dev_client.get(
                f"/api/v1/api-keys/{api_key_id}",
                headers=auth_headers,
            )
            assert detail.status_code == 200, detail.text
            assert detail.json()["usage_count"] >= 1
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_vkey_rejects_conflicting_x_team_id_header(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """sk-gw-* 绑定团队；冲突的 X-Team-Id 应 400，而非静默 override。"""
        try:
            team = await TeamService(db_session).ensure_personal_team(test_user.id)
            other = await TeamService(db_session).create_team(
                name="Other VKey Header Team",
                owner_user_id=test_user.id,
            )
            await db_session.commit()

            ck = await dev_client.post(
                f"/api/v1/gateway/teams/{team.id}/keys",
                headers=auth_headers,
                json={"name": "itest-vkey-header-guard"},
            )
            assert ck.status_code == 201, ck.text
            plain_key = ck.json()["plain_key"]

            ok = await dev_client.get(
                _OPENAI_MODELS,
                headers={"Authorization": f"Bearer {plain_key}"},
            )
            assert ok.status_code == 200, ok.text

            bad = await dev_client.get(
                _OPENAI_MODELS,
                headers={
                    "Authorization": f"Bearer {plain_key}",
                    "X-Team-Id": str(other.id),
                },
            )
            assert bad.status_code == 400, bad.text
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_chat_completions_exposes_gateway_timing_headers(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        try:
            model_name, plain_key = await _setup_team_model_vkey(
                dev_client, auth_headers, db_session, test_user
            )

            async def _acompletion(_self: Any, **kwargs: Any) -> Any:
                return _fake_chat_completion(stream=bool(kwargs.get("stream")))

            monkeypatch.setattr("litellm.router.Router.acompletion", _acompletion)

            bearer = {"Authorization": f"Bearer {plain_key}"}
            non_stream = await dev_client.post(
                _OPENAI_CHAT,
                headers=bearer,
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )
            assert non_stream.status_code == 200, non_stream.text
            assert HEADER_GATEWAY_PREFLIGHT_MS in non_stream.headers
            assert HEADER_GATEWAY_UPSTREAM_MS in non_stream.headers
            assert int(non_stream.headers[HEADER_GATEWAY_PREFLIGHT_MS]) >= 0
            assert int(non_stream.headers[HEADER_GATEWAY_UPSTREAM_MS]) >= 0
            await shutdown_proxy_deferred_tasks()

            stream = await dev_client.post(
                _OPENAI_CHAT,
                headers=bearer,
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True,
                },
            )
            assert stream.status_code == 200, stream.text
            assert HEADER_GATEWAY_PREFLIGHT_MS in stream.headers
            assert HEADER_GATEWAY_UPSTREAM_MS not in stream.headers
            async for _chunk in stream.aiter_bytes():
                pass
            await shutdown_proxy_deferred_tasks()
        finally:
            clear_permission_context()
