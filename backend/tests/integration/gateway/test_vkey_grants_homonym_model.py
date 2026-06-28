"""多 team 同名模型派发集成测试。"""

from __future__ import annotations

import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from bootstrap.config import settings
from domains.gateway.application.usage.gateway_vkey_metrics import (
    AMBIGUOUS_MODEL_INVOCATIONS_TOTAL,
    export_vkey_metrics,
    reset_vkey_metrics_for_tests,
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
_OPENAI_EMBED = f"{openai_compat_base()}/embeddings"


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
    return types.SimpleNamespace(id="homonym", choices=[choice], usage=usage, model=model)


@pytest.mark.integration
class TestVkeyGrantsHomonymModel:
    @pytest.mark.asyncio
    async def test_unprefixed_strict_rejects_homonym(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "gateway_vkey_strict_team_prefix", True)
        primary, shared = await ensure_two_teams(db_session, test_user)
        model_name = "gpt-4o"
        await setup_team_model(dev_client, primary.id, auth_headers, model_name=model_name)
        await setup_team_model(dev_client, shared.id, auth_headers, model_name=model_name)
        vkey_id, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 400, r.text
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_explicit_prefix_hits_grant_team(
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
        model_name = "gpt-4o"
        await setup_team_model(dev_client, primary.id, auth_headers, model_name=model_name)
        await setup_team_model(dev_client, shared_id, auth_headers, model_name=model_name)
        _, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)
        r_keys = await dev_client.get(
            f"/api/v1/gateway/teams/{primary.id}/keys", headers=auth_headers
        )
        vkey_id = r_keys.json()[-1]["id"]
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
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
        assert captured.get("gateway_team_id") == str(shared_id)
        assert captured.get("gateway_dispatched_via_prefix") is True
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_embeddings_prefix_dispatch(
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
        embed_name = f"emb-{uuid.uuid4().hex[:6]}"
        await setup_team_model(
            dev_client, shared_id, auth_headers, model_name=embed_name, capability="embedding"
        )
        vkey_id, plain_key = await create_vkey_with_plain(dev_client, primary.id, auth_headers)
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary.id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared_id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        captured: dict[str, Any] = {}

        async def _aembedding(_self: object, **kwargs: Any) -> Any:
            meta = kwargs.get("metadata")
            if isinstance(meta, dict):
                captured.update(meta)
            return types.SimpleNamespace(data=[], model=str(kwargs.get("model")))

        monkeypatch.setattr("litellm.router.Router.aembedding", _aembedding)

        r = await dev_client.post(
            _OPENAI_EMBED,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={"model": f"{shared_slug}/{embed_name}", "input": "hello"},
        )
        assert r.status_code == 200, r.text
        assert captured.get("gateway_team_id") == str(shared_id)
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_unprefixed_hits_primary_only(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        primary, shared = await ensure_two_teams(db_session, test_user)
        primary_id = primary.id
        shared_id = shared.id
        model_name = "gpt-4o"
        await setup_team_model(dev_client, primary_id, auth_headers, model_name=model_name)
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
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200, r.text
        assert captured.get("gateway_team_id") == str(primary_id)
        assert captured.get("gateway_dispatched_via_prefix") is False
        await shutdown_proxy_deferred_tasks()

    @pytest.mark.asyncio
    async def test_unprefixed_homonym_records_metric_non_strict(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """非 strict：无前缀同名模型记指标但仍落主属 team。"""
        monkeypatch.setattr(settings, "gateway_vkey_strict_team_prefix", False)
        reset_vkey_metrics_for_tests()
        primary, shared = await ensure_two_teams(db_session, test_user)
        primary_id = primary.id
        model_name = f"homonym-{uuid.uuid4().hex[:6]}"
        await setup_team_model(dev_client, primary_id, auth_headers, model_name=model_name)
        await setup_team_model(dev_client, shared.id, auth_headers, model_name=model_name)
        vkey_id, plain_key = await create_vkey_with_plain(dev_client, primary_id, auth_headers)
        r_grant = await dev_client.post(
            f"/api/v1/gateway/teams/{primary_id}/keys/{vkey_id}/grants",
            headers=auth_headers,
            json={"tenant_ids": [str(shared.id)]},
        )
        assert r_grant.status_code == 201, r_grant.text
        await reload_router(db_session)

        patch_router_acompletion(monkeypatch, _fake_chat_completion(model=model_name))
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200, r.text
        metrics = export_vkey_metrics()
        assert any(
            AMBIGUOUS_MODEL_INVOCATIONS_TOTAL in key and model_name in key
            for key in metrics
        )
        await shutdown_proxy_deferred_tasks()
