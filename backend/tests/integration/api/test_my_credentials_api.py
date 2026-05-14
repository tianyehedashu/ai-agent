"""用户私有凭据 GET/POST/PATCH/DELETE /api/v1/gateway/my-credentials 集成测试"""

import uuid

from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestMyCredentialsAPI:
    @pytest.mark.asyncio
    async def test_list_my_credentials_unauthorized(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/gateway/my-credentials")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_crud_my_credential(self, client: AsyncClient, auth_headers: dict) -> None:
        r0 = await client.get("/api/v1/gateway/my-credentials", headers=auth_headers)
        assert r0.status_code == 200
        initial = len(r0.json())

        r1 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json={
                "provider": "deepseek",
                "name": "integration-test-acct",
                "api_key": "sk-test-placeholder",
                "api_base": None,
            },
        )
        assert r1.status_code == 201, r1.text
        body = r1.json()
        cid = body["id"]
        assert body["provider"] == "deepseek"
        assert body["name"] == "integration-test-acct"

        r2 = await client.get("/api/v1/gateway/my-credentials", headers=auth_headers)
        assert r2.status_code == 200
        assert len(r2.json()) == initial + 1

        r3 = await client.patch(
            f"/api/v1/gateway/my-credentials/{cid}",
            headers=auth_headers,
            json={"api_base": "https://example.invalid/v1"},
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["api_base"] == "https://example.invalid/v1"

        r4 = await client.delete(f"/api/v1/gateway/my-credentials/{cid}", headers=auth_headers)
        assert r4.status_code == 204

        r5 = await client.get("/api/v1/gateway/my-credentials", headers=auth_headers)
        assert len(r5.json()) == initial

    @pytest.mark.asyncio
    async def test_create_duplicate_my_credential_returns_409(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        name = f"dup-name-{uuid.uuid4().hex[:12]}"
        payload = {
            "provider": "deepseek",
            "name": name,
            "api_key": "sk-test-placeholder",
            "api_base": None,
        }
        r1 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json=payload,
        )
        assert r1.status_code == 201, r1.text
        cid = r1.json()["id"]

        r2 = await client.post(
            "/api/v1/gateway/my-credentials",
            headers=auth_headers,
            json=payload,
        )
        assert r2.status_code == 409, r2.text

        r3 = await client.delete(f"/api/v1/gateway/my-credentials/{cid}", headers=auth_headers)
        assert r3.status_code == 204
