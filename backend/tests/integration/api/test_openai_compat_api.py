"""
OpenAI 兼容入口 /v1/* 集成测试（虚拟 Key + dev_client）。
"""

from __future__ import annotations

from httpx import AsyncClient
import pytest

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
