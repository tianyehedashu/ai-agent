"""vkey grants 审计 tenant_id 落点集成测试。"""

from __future__ import annotations

import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.infrastructure.router_singleton import reload_router
from libs.api.paths import openai_compat_base
from tests.integration.gateway.vkey_grant_helpers import (
    create_vkey_with_plain,
    ensure_two_teams,
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
    return types.SimpleNamespace(id="audit", choices=[choice], usage=usage, model="m")


@pytest.mark.integration
class TestVkeyGrantsAuditAttribution:
    @pytest.mark.asyncio
    async def test_dispatch_metadata_team_id_is_effective_team(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        shared_id = shared.id
        shared_slug = shared.slug
        primary_id = primary.id
        model_name = f"audit-{uuid.uuid4().hex[:6]}"
        await setup_team_model(dev_client, shared_id, auth_headers, model_name=model_name)
        vkey_id, plain_key = await create_vkey_with_plain(dev_client, primary_id, auth_headers)
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary_id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared_id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        captured: dict[str, Any] = {}

        async def _acompletion(_self: object, **kwargs: Any) -> Any:
            meta = kwargs.get("metadata")
            if isinstance(meta, dict):
                captured.update(meta)
            return _fake_chat_completion()

        monkeypatch.setattr("litellm.router.Router.acompletion", _acompletion)

        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={
                "model": f"{shared_slug}/{model_name}",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code == 200, r.text
        await shutdown_proxy_deferred_tasks()

        assert captured.get("gateway_team_id") == str(shared_id)
        assert captured.get("gateway_vkey_owner_team_id") == str(primary_id)
        assert captured.get("gateway_dispatched_via_prefix") is True
        assert captured.get("gateway_route_name") == f"{shared_slug}/{model_name}"
