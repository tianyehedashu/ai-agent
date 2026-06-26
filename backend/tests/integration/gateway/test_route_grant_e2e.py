"""路由即可共享模型 · 端到端集成：发布 → 列表暴露 → 委派调用归因 → 撤销失效。"""

from __future__ import annotations

import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from domains.gateway.infrastructure.router_singleton import reload_router
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.api.paths import openai_compat_base
from libs.iam.permission_context import clear_permission_context

_OPENAI_MODELS = f"{openai_compat_base()}/models"
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
        id="chatcmpl-test", choices=[choice], usage=usage, model="gpt-4o-mini"
    )


def _model_ids(payload: dict[str, object]) -> set[str]:
    data = payload.get("data")
    assert isinstance(data, list)
    return {item["id"] for item in data if isinstance(item, dict)}


async def _seed_team_model(
    dev_client: AsyncClient, team_id: uuid.UUID, headers: dict[str, str], *, model_name: str
) -> None:
    cred = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/credentials",
        headers=headers,
        json={
            "provider": "openai",
            "name": f"cred-{uuid.uuid4().hex[:6]}",
            "api_key": "sk-route-share-e2e-key-123456789",
            "scope": "team",
        },
    )
    assert cred.status_code == 201, cred.text
    model = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/models",
        headers=headers,
        json={
            "name": model_name,
            "capability": "chat",
            "real_model": "gpt-4o-mini",
            "credential_id": cred.json()["id"],
            "provider": "openai",
        },
    )
    assert model.status_code == 201, model.text


@pytest.mark.integration
class TestRouteGrantE2E:
    @pytest.mark.asyncio
    async def test_publish_invoke_attribute_revoke(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        try:
            teams = TeamService(db_session)
            personal = await teams.ensure_personal_team(test_user.id)
            consumer_team = await teams.create_team(
                name=f"consumer-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
            )
            await db_session.commit()

            # 个人路由（owner = 当前用户）发布给消费团队
            model_name = f"m-{uuid.uuid4().hex[:6]}"
            await _seed_team_model(
                dev_client, personal.id, auth_headers, model_name=model_name
            )
            r_route = await dev_client.post(
                "/api/v1/gateway/my-routes",
                headers=auth_headers,
                json={
                    "virtual_model": f"vm-{uuid.uuid4().hex[:6]}",
                    "primary_models": [model_name],
                },
            )
            assert r_route.status_code == 201, r_route.text
            route_id = r_route.json()["id"]

            alias = f"shared-{uuid.uuid4().hex[:6]}"
            r_grant = await dev_client.post(
                f"/api/v1/gateway/my-routes/{route_id}/grants",
                headers=auth_headers,
                json={"target_tenant_id": str(consumer_team.id), "exposed_alias": alias},
            )
            assert r_grant.status_code == 201, r_grant.text
            assert r_grant.json()["exposed_alias"] == alias

            # owner 侧列表 / 团队侧共享列表
            r_list = await dev_client.get(
                f"/api/v1/gateway/my-routes/{route_id}/grants", headers=auth_headers
            )
            assert r_list.status_code == 200, r_list.text
            assert any(g["tenant_id"] == str(consumer_team.id) for g in r_list.json())

            r_shared = await dev_client.get(
                f"/api/v1/gateway/teams/{consumer_team.id}/shared-routes",
                headers=auth_headers,
            )
            assert r_shared.status_code == 200, r_shared.text
            shared_payload = r_shared.json()
            assert any(s["exposed_alias"] == alias for s in shared_payload)
            shared_row = next(s for s in shared_payload if s["exposed_alias"] == alias)
            assert shared_row["primary_models"] == [model_name]
            assert shared_row["enabled"] is True

            # 消费团队 vkey
            r_key = await dev_client.post(
                f"/api/v1/gateway/teams/{consumer_team.id}/keys",
                headers=auth_headers,
                json={"name": f"vkey-{uuid.uuid4().hex[:8]}"},
            )
            assert r_key.status_code == 201, r_key.text
            plain_key = r_key.json()["plain_key"]
            await reload_router(db_session)

            # /v1/models 暴露暴露别名
            r_models = await dev_client.get(
                _OPENAI_MODELS, headers={"Authorization": f"Bearer {plain_key}"}
            )
            assert r_models.status_code == 200, r_models.text
            assert alias in _model_ids(r_models.json())

            # 委派调用：捕获 Router kwargs 验证编码与归因
            captured: dict[str, Any] = {}

            async def _acompletion(_self: Any, **kwargs: Any) -> Any:
                captured.update(kwargs)
                return _fake_chat_completion()

            monkeypatch.setattr("litellm.router.Router.acompletion", _acompletion)

            r_chat = await dev_client.post(
                _OPENAI_CHAT,
                headers={"Authorization": f"Bearer {plain_key}"},
                json={
                    "model": alias,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )
            assert r_chat.status_code == 200, r_chat.text
            # deployment 注册在消费团队命名空间
            assert captured.get("model") == f"gw/t/{consumer_team.id}/{alias}"
            # 用量归因到路由创建者（共享出资源的人）
            meta = captured.get("metadata") or {}
            assert meta.get("gateway_resource_owner_user_id") == str(test_user.id)
            # 计费团队是消费团队
            assert meta.get("gateway_team_id") == str(consumer_team.id)
            route_snap = meta.get("gateway_route_snapshot") or {}
            assert route_snap.get("delegated") is True
            assert route_snap.get("exposed_alias") == alias

            # 撤销后失效：列表移除 + 调用 404
            r_revoke = await dev_client.delete(
                f"/api/v1/gateway/my-routes/{route_id}/grants/{consumer_team.id}",
                headers=auth_headers,
            )
            assert r_revoke.status_code == 204, r_revoke.text
            await reload_router(db_session)

            r_models2 = await dev_client.get(
                _OPENAI_MODELS, headers={"Authorization": f"Bearer {plain_key}"}
            )
            assert r_models2.status_code == 200
            assert alias not in _model_ids(r_models2.json())

            r_chat2 = await dev_client.post(
                _OPENAI_CHAT,
                headers={"Authorization": f"Bearer {plain_key}"},
                json={
                    "model": alias,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )
            assert r_chat2.status_code != 200
        finally:
            clear_permission_context()

    @pytest.mark.asyncio
    async def test_grant_requires_route_ownership(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
        db_session,
        test_user: User,
    ) -> None:
        """非创建者发布他人路由 → 404（防枚举）。"""
        try:
            teams = TeamService(db_session)
            other = User(
                email=f"other-{uuid.uuid4().hex[:8]}@example.com",
                hashed_password="hashed_password",
                name="Other",
            )
            db_session.add(other)
            await db_session.flush()
            other_team = await teams.create_team(
                name=f"other-{uuid.uuid4().hex[:6]}", owner_user_id=other.id
            )
            from domains.gateway.infrastructure.repositories.gateway_route_repository import (
                GatewayRouteRepository,
            )

            route = await GatewayRouteRepository(db_session).create(
                tenant_id=other_team.id,
                virtual_model=f"vm-{uuid.uuid4().hex[:6]}",
                primary_models=["x"],
                created_by_user_id=other.id,
            )
            my_team = await teams.create_team(
                name=f"mine-{uuid.uuid4().hex[:6]}", owner_user_id=test_user.id
            )
            await db_session.commit()

            r = await dev_client.post(
                f"/api/v1/gateway/my-routes/{route.id}/grants",
                headers=auth_headers,
                json={"target_tenant_id": str(my_team.id)},
            )
            assert r.status_code == 404, r.text
        finally:
            clear_permission_context()
