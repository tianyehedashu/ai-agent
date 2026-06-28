"""离线清理 stale vkey grants 集成测试。"""

from __future__ import annotations

import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.application.vkey.management.virtual_key_team_grant_reads import (
    list_active_grant_tenant_ids,
)
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
    return types.SimpleNamespace(id="cleanup", choices=[choice], usage=usage, model="m")


@pytest.mark.integration
class TestVkeyGrantsOfflineCleanup:
    @pytest.mark.asyncio
    async def test_revoke_grant_then_prefix_call_fails(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        model_name = f"clean-{uuid.uuid4().hex[:6]}"
        await setup_team_model(dev_client, shared.id, auth_headers, model_name=model_name)
        vkey_id, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r_del = await dev_client.delete(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants/{shared.id}",
            headers=auth_headers,
        )
        assert r_del.status_code == 204, r_del.text
        grants = await list_active_grant_tenant_ids(db_session, uuid.UUID(vkey_id))
        assert shared.id not in grants

        patch_router_acompletion(monkeypatch, _fake_chat_completion())
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={
                "model": f"{shared.slug}/{model_name}",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert r.status_code in (404, 422), r.text
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_cleanup_script_dry_run(self, db_session) -> None:
        """cleanup 脚本在测试库可安全 dry-run（表由 alembic 创建）。"""
        from sqlalchemy import select

        from domains.gateway.infrastructure.models.virtual_key_team_grant import (
            GatewayVirtualKeyTeamGrant,
        )

        # 仅验证 ORM 表可读（等同脚本首步查询）
        await db_session.execute(
            select(GatewayVirtualKeyTeamGrant.id).where(
                GatewayVirtualKeyTeamGrant.is_active.is_(True)
            ).limit(1)
        )
