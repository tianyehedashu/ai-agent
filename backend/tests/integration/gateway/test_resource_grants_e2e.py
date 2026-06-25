"""个人资源 grant：管理 API + 代理解析 E2E。"""

from __future__ import annotations

import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.gateway_model_listing import resolve_by_name_visible
from domains.gateway.application.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.infrastructure.router_singleton import reload_router
from libs.api.paths import openai_compat_base
from tests.integration.gateway.resource_grant_helpers import (
    grant_model_to_teams,
    setup_personal_byok_model,
)
from tests.integration.gateway.vkey_grant_helpers import (
    create_vkey_with_plain,
    ensure_two_teams,
    patch_router_acompletion,
)

_OPENAI_CHAT = f"{openai_compat_base()}/chat/completions"


def _fake_chat_completion(*, model: str = "gpt-4o-mini") -> Any:
    message = types.SimpleNamespace(content="ok", tool_calls=None, reasoning_content=None)
    choice = types.SimpleNamespace(message=message, finish_reason="stop", delta=None)
    usage = types.SimpleNamespace(
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        prompt_tokens_details={},
        completion_tokens_details={},
    )
    return types.SimpleNamespace(id="gr-grant", choices=[choice], usage=usage, model=model)


@pytest.mark.integration
class TestResourceGrantsE2e:
    @pytest.mark.asyncio
    async def test_resource_grant_api_list_create_revoke(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        _, model_id, model_name = await setup_personal_byok_model(
            dev_client, auth_headers, model_name=f"api-gr-{uuid.uuid4().hex[:6]}"
        )
        grants = await grant_model_to_teams(
            dev_client,
            auth_headers,
            model_id=model_id,
            target_team_ids=[shared.id],
        )
        assert len(grants) == 1
        assert grants[0]["target_team_id"] == str(shared.id)
        grant_id = grants[0]["id"]

        r_list = await dev_client.get("/api/v1/gateway/resource-grants", headers=auth_headers)
        assert r_list.status_code == 200, r_list.text
        assert any(g["id"] == grant_id for g in r_list.json())

        r_team = await dev_client.get(
            f"/api/v1/gateway/teams/{shared.id}/granted-resources/models",
            headers=auth_headers,
        )
        assert r_team.status_code == 200, r_team.text
        team_rows = r_team.json()
        assert any(row["name"] == model_name for row in team_rows)
        assert team_rows[0]["owner_user_id"] == str(test_user.id)

        r_patch = await dev_client.patch(
            f"/api/v1/gateway/resource-grants/{grant_id}",
            headers=auth_headers,
            json={"enabled": False},
        )
        assert r_patch.status_code == 200, r_patch.text
        assert r_patch.json()["enabled"] is False

        r_del = await dev_client.delete(
            f"/api/v1/gateway/resource-grants/{grant_id}",
            headers=auth_headers,
        )
        assert r_del.status_code == 204, r_del.text
        _ = primary

    @pytest.mark.asyncio
    async def test_vkey_proxy_resolves_granted_model(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        _, model_id, model_name = await setup_personal_byok_model(
            dev_client, auth_headers, model_name=f"proxy-gr-{uuid.uuid4().hex[:6]}"
        )
        await grant_model_to_teams(
            dev_client,
            auth_headers,
            model_id=model_id,
            target_team_ids=[shared.id],
        )
        await reload_router(db_session)

        resolved = await resolve_by_name_visible(db_session, shared.id, model_name)
        assert resolved is not None
        assert resolved.tenant_id == primary.id

        _, plain_key = await create_vkey_with_plain(dev_client, shared.id, auth_headers)
        patch_router_acompletion(monkeypatch, _fake_chat_completion(model=model_name))

        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200, r.text
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_slug_prefix_resolves_granted_model_on_proxy(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        _, model_id, model_name = await setup_personal_byok_model(
            dev_client, auth_headers, model_name=f"slug-proxy-{uuid.uuid4().hex[:6]}"
        )
        await grant_model_to_teams(
            dev_client,
            auth_headers,
            model_id=model_id,
            target_team_ids=[shared.id],
        )
        await reload_router(db_session)

        _, plain_key = await create_vkey_with_plain(dev_client, shared.id, auth_headers)
        patch_router_acompletion(monkeypatch, _fake_chat_completion(model=model_name))

        prefixed = f"{primary.slug}/{model_name}"
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={"model": prefixed, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200, r.text
        await shutdown_proxy_deferred_tasks()
