"""
Health Check Tests - 健康检查测试
"""

from httpx import AsyncClient
import pytest


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """测试健康检查端点"""
    response = await client.get("/api/v1/system/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    """测试根端点"""
    response = await client.get("/")
    assert response.status_code == 200

    data = response.json()
    assert "message" in data
