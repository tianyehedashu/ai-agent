"""跨 team prefix 派发 E2E 集成测试。"""

from __future__ import annotations

import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.proxy.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.infrastructure.litellm.router_singleton import reload_router
from libs.api.paths import openai_compat_base
from tests.integration.gateway.vkey_grant_helpers import (
    create_vkey_with_plain,
    ensure_two_teams,
    patch_router_acompletion,
    setup_team_model,
)

_OPENAI_CHAT = f"{openai_compat_base()}/chat/completions"


def _fake_chat_completion() -> Any:
    message = types.SimpleNamespace(content="ok", tool_calls=None, reasoning_content=None)
    choice = types.SimpleNamespace(message=message, finish_reason="stop", delta=None)
    usage = types.SimpleNamespace(
        prompt_tokens=3,
        completion_tokens=2,
        total_tokens=5,
        prompt_tokens_details={},
        completion_tokens_details={},
    )
    return types.SimpleNamespace(
        id="chatcmpl-test",
        choices=[choice],
        usage=usage,
        model="gpt-4o-mini",
    )


async def _latest_vkey_id(
    dev_client: AsyncClient, team_id: uuid.UUID, headers: dict[str, str]
) -> str:
    r = await dev_client.get(f"/api/v1/gateway/teams/{team_id}/keys", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()
    assert items
    return items[-1]["id"]


@pytest.mark.integration
class TestMultiTenantVkeyDispatchE2e:
    @pytest.mark.asyncio
    async def test_prefix_dispatch_hits_grant_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        model_name = f"mv-{uuid.uuid4().hex[:6]}"
        await setup_team_model(dev_client, shared.id, auth_headers, model_name=model_name)
        _, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)
        vkey_id = await _latest_vkey_id(dev_client, primary.id, auth_headers)
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        patch_router_acompletion(monkeypatch, _fake_chat_completion())

        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={
                "model": f"{shared.slug}/{model_name}",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 200, r.text
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_no_prefix_on_primary_without_model_returns_422(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        model_name = f"only-y-{uuid.uuid4().hex[:6]}"
        await setup_team_model(dev_client, shared.id, auth_headers, model_name=model_name)
        _, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)
        vkey_id = await _latest_vkey_id(dev_client, primary.id, auth_headers)
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        patch_router_acompletion(monkeypatch, _fake_chat_completion())

        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code in (404, 422), r.text
        await shutdown_proxy_deferred_tasks()
