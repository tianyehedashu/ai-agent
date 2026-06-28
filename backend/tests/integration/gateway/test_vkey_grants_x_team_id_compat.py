"""X-Team-Id 与 grants 兼容集成测试。"""

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
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        prompt_tokens_details={},
        completion_tokens_details={},
    )
    return types.SimpleNamespace(id="x", choices=[choice], usage=usage, model="m")


async def _grant_and_model(
    dev_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
    test_user,
) -> tuple[Any, Any, str, str]:
    primary, shared = await ensure_two_teams(db_session, test_user)
    model_name = f"xteam-{uuid.uuid4().hex[:6]}"
    await setup_team_model(dev_client, primary.id, auth_headers, model_name=model_name)
    _, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)
    r_keys = await dev_client.get(
        f"/api/v1/gateway/teams/{primary.id}/keys", headers=auth_headers
    )
    vkey_id = r_keys.json()[-1]["id"]
    r_grant = await dev_client.post(
        f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
        headers=auth_headers,
        json={"tenant_ids": [str(shared.id)]},
    )
    assert r_grant.status_code == 201, r_grant.text
    await reload_router(db_session)
    return primary, shared, plain_key, model_name


@pytest.mark.integration
class TestVkeyGrantsXTeamIdCompat:
    @pytest.mark.asyncio
    async def test_header_bound_team_ok(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, _, plain_key, model_name = await _grant_and_model(
            dev_client, auth_headers, db_session, test_user
        )
        patch_router_acompletion(monkeypatch, _fake_chat_completion())
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={
                "Authorization": f"Bearer {plain_key}",
                "X-Team-Id": str(primary.id),
            },
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200, r.text
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_header_grant_team_ok(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared, plain_key, model_name = await _grant_and_model(
            dev_client, auth_headers, db_session, test_user
        )
        await setup_team_model(dev_client, shared.id, auth_headers, model_name=model_name)
        await reload_router(db_session)
        patch_router_acompletion(monkeypatch, _fake_chat_completion())
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={
                "Authorization": f"Bearer {plain_key}",
                "X-Team-Id": str(shared.id),
            },
            json={
                "model": f"{shared.slug}/{model_name}",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 200, r.text
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_header_non_grant_team_rejected(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        _, _, plain_key, model_name = await _grant_and_model(
            dev_client, auth_headers, db_session, test_user
        )
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={
                "Authorization": f"Bearer {plain_key}",
                "X-Team-Id": str(uuid.uuid4()),
            },
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 400, r.text
