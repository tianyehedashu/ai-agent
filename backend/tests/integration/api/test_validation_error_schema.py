"""422 字段校验 Problem Details 集成测试。"""

from __future__ import annotations

from httpx import AsyncClient
import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validation_error_includes_errors_array(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/token/refresh",
        json={},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["status"] == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body.get("errors"), list)
    assert len(body["errors"]) >= 1
    first = body["errors"][0]
    assert "loc" in first
    assert "msg" in first
    assert "type" in first
