"""
OpenAI 兼容入口 /v1/* 集成测试（虚拟 Key + dev_client）。
"""

from __future__ import annotations

from httpx import AsyncClient
import pytest

from domains.identity.domain.api_key_types import ApiKeyScope
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.db.permission_context import clear_permission_context


@pytest.mark.integration
class TestOpenAiCompatApi:
    @pytest.mark.asyncio
    async def test_v1_models_requires_bearer(self, dev_client: AsyncClient) -> None:
        r = await dev_client.get("/v1/models")
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

            mgmt_headers = {**auth_headers, "X-Team-Id": str(team.id)}
            ck = await dev_client.post(
                "/api/v1/gateway/keys",
                headers=mgmt_headers,
                json={"name": "itest-openai-compat-models"},
            )
            assert ck.status_code == 201, ck.text
            plain_key = ck.json()["plain_key"]

            r = await dev_client.get(
                "/v1/models",
                headers={"Authorization": f"Bearer {plain_key}"},
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("object") == "list"
            assert isinstance(body.get("data"), list)
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
                "/api/v1/api-keys",
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
                "/v1/models",
                headers={"Authorization": f"Bearer {plain_key}"},
            )
            assert personal_models.status_code == 200, personal_models.text

            shared_denied = await dev_client.get(
                "/v1/models",
                headers={
                    "Authorization": f"Bearer {plain_key}",
                    "X-Team-Id": str(shared.id),
                },
            )
            assert shared_denied.status_code == 403, shared_denied.text

            bad_team_header = await dev_client.get(
                "/v1/models",
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
                "/api/v1/api-keys",
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
                "/v1/models",
                headers={
                    "Authorization": f"Bearer {plain_key}",
                    "X-Team-Id": str(shared.id),
                },
            )
            assert selected.status_code == 200, selected.text
        finally:
            clear_permission_context()
