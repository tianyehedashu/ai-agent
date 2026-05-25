"""管理面 API 错误响应 RFC 7807 schema 集成测试。"""

from __future__ import annotations

from httpx import AsyncClient
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_not_found_returns_problem_details(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000099",
        headers=auth_headers,
    )
    assert response.status_code == 404
    body = response.json()
    assert body["status"] == 404
    assert body["code"] == "NOT_FOUND"
    assert "detail" in body
    assert "title" in body
    assert "type" in body
    assert body["type"].startswith("https://ai-agent.local/errors/")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unauthenticated_returns_problem_details(client: AsyncClient) -> None:
    response = await client.get("/api/v1/sessions/")
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == 401
    assert body["code"] in ("AUTHENTICATION_ERROR", "TOKEN_ERROR")
    assert "detail" in body
    assert "title" in body
