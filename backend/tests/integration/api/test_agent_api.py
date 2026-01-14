"""
Agent API 集成测试

测试 Agent API 端点的完整功能
"""

from fastapi import status
from httpx import AsyncClient
import pytest

# Fixtures 从 conftest.py 自动导入


class TestAgentAPI:
    """Agent API 集成测试"""

    @pytest.mark.asyncio
    async def test_list_agents_requires_auth(self, client: AsyncClient):
        """测试: 列出 Agents 需要认证"""
        # Act
        response = await client.get("/api/v1/agents")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_agents(self, client: AsyncClient, auth_headers: dict):
        """测试: 列出 Agents"""
        # Act
        response = await client.get("/api/v1/agents", headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list | dict)
        # 如果是列表
        if isinstance(data, list):
            assert all("id" in item for item in data)

    @pytest.mark.asyncio
    async def test_create_agent(self, client: AsyncClient, auth_headers: dict):
        """测试: 创建 Agent"""
        # Arrange
        agent_data = {
            "name": "Test Agent",
            "system_prompt": "You are a helpful assistant.",
            "model": "gpt-4",
        }

        # Act
        response = await client.post(
            "/api/v1/agents",
            json=agent_data,
            headers=auth_headers,
        )

        # Assert
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        ]
        data = response.json()
        assert data["name"] == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_agent_by_id(self, client: AsyncClient, auth_headers: dict):
        """测试: 根据 ID 获取 Agent"""
        # Arrange - 先创建一个 Agent
        create_response = await client.post(
            "/api/v1/agents",
            json={"name": "Test Agent", "system_prompt": "Test"},
            headers=auth_headers,
        )
        agent_id = create_response.json()["id"]

        # Act
        response = await client.get(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == agent_id

    @pytest.mark.asyncio
    async def test_update_agent(self, client: AsyncClient, auth_headers: dict):
        """测试: 更新 Agent"""
        # Arrange - 先创建一个 Agent
        create_response = await client.post(
            "/api/v1/agents",
            json={"name": "Test Agent", "system_prompt": "Test"},
            headers=auth_headers,
        )
        agent_id = create_response.json()["id"]

        # Act
        response = await client.put(
            f"/api/v1/agents/{agent_id}",
            json={"name": "Updated Agent"},
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Agent"

    @pytest.mark.asyncio
    async def test_delete_agent(self, client: AsyncClient, auth_headers: dict):
        """测试: 删除 Agent"""
        # Arrange - 先创建一个 Agent
        create_response = await client.post(
            "/api/v1/agents",
            json={"name": "Test Agent", "system_prompt": "Test"},
            headers=auth_headers,
        )
        agent_id = create_response.json()["id"]

        # Act
        response = await client.delete(
            f"/api/v1/agents/{agent_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_204_NO_CONTENT,
        ]
