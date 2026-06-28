"""delete_shared_team 同步撤销 vkey 跨团队授权集成测试。"""

from __future__ import annotations

import types
from typing import Any
import uuid

import pytest

from domains.gateway.application.proxy.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.application.vkey.management.virtual_key_team_grant_reads import (
    list_active_grants_for_vkey,
)
from domains.gateway.infrastructure.litellm.router_singleton import reload_router
from domains.tenancy.application.team_service import TeamService
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
    return types.SimpleNamespace(id="del-team", choices=[choice], usage=usage, model="m")


@pytest.mark.integration
class TestDeleteSharedTeamRevokesVkeyGrants:
    @pytest.mark.asyncio
    async def test_delete_shared_team_revokes_grants_and_blocks_prefix_call(
        self,
        dev_client,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        shared_id = shared.id
        shared_slug = shared.slug
        model_name = f"del-{uuid.uuid4().hex[:6]}"
        await setup_team_model(dev_client, shared_id, auth_headers, model_name=model_name)
        vkey_id, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)

        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared_id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        grants_before = await list_active_grants_for_vkey(db_session, uuid.UUID(vkey_id))
        assert any(g.tenant_id == shared_id and g.is_active for g in grants_before)

        await TeamService(db_session).delete_shared_team(shared_id)
        await db_session.commit()
        await reload_router(db_session)

        grants_after = await list_active_grants_for_vkey(db_session, uuid.UUID(vkey_id))
        assert not any(g.tenant_id == shared_id and g.is_active for g in grants_after)

        patch_router_acompletion(monkeypatch, _fake_chat_completion())
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={
                "model": f"{shared_slug}/{model_name}",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code in (404, 422), r.text
        await shutdown_proxy_deferred_tasks()
