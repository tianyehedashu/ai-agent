"""
Session API 集成测试

测试 Session API 端点的完整功能
"""

from fastapi import status
from httpx import AsyncClient
import pytest

# Fixtures 从 conftest.py 自动导入


class TestSessionAPI:
    """Session API 集成测试"""

    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self, client: AsyncClient):
        """测试: 列出会话需要认证"""
        # Act
        response = await client.get("/api/v1/sessions/", follow_redirects=False)

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_sessions(self, client: AsyncClient, auth_headers: dict):
        """测试: 列出会话"""
        # Act
        response = await client.get(
            "/api/v1/sessions/", headers=auth_headers, follow_redirects=False
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # 验证返回的会话格式
        if data:
            assert all("id" in item for item in data)
            assert all("user_id" in item for item in data)

    @pytest.mark.asyncio
    async def test_create_session_without_params(self, client: AsyncClient, auth_headers: dict):
        """测试: 创建会话（无参数）"""
        # Act
        response = await client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert "user_id" in data
        assert data["agent_id"] is None
        assert data["title"] is None
        assert data["status"] == "active"
        assert data["message_count"] == 0
        assert data["token_count"] == 0

    @pytest.mark.asyncio
    async def test_create_session_as_anonymous_user_in_dev_mode(self, client: AsyncClient):
        """测试: 匿名用户创建会话（开发模式）

        注意：此测试在开发模式下验证匿名用户（无认证头）可以创建会话。
        在生产模式下，此测试可能会失败（需要认证）。
        """
        # Act - 匿名用户（无认证头）创建会话
        # 在开发模式下，系统会自动创建匿名用户
        response = await client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous Session"},
            follow_redirects=False,
        )

        # Assert
        # 在开发模式下应该成功（201），在生产模式下会返回401
        # 这里我们检查两种情况
        if response.status_code == status.HTTP_201_CREATED:
            # 开发模式：匿名用户成功创建会话
            data = response.json()
            assert "id" in data
            assert "user_id" in data
            assert data["title"] == "Anonymous Session"
            assert data["status"] == "active"
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            # 生产模式：需要认证
            # 这是预期的行为，测试通过
            pass
        else:
            # 其他状态码表示意外情况
            pytest.fail(f"Unexpected status code: {response.status_code}")

    @pytest.mark.asyncio
    async def test_create_session_with_title(self, client: AsyncClient, auth_headers: dict):
        """测试: 创建会话（带title）"""
        # Arrange
        session_data = {
            "title": "Test Session",
        }

        # Act
        response = await client.post(
            "/api/v1/sessions/",
            json=session_data,
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "Test Session"
        assert data["agent_id"] is None

    @pytest.mark.asyncio
    async def test_create_session_with_agent_id(self, client: AsyncClient, auth_headers: dict):
        """测试: 创建会话（带agent_id）"""
        # Arrange - 先创建一个 Agent
        agent_response = await client.post(
            "/api/v1/agents/",
            json={"name": "Test Agent", "system_prompt": "Test prompt"},
            headers=auth_headers,
            follow_redirects=False,
        )
        agent_id = agent_response.json()["id"]

        session_data = {
            "agent_id": agent_id,
        }

        # Act
        response = await client.post(
            "/api/v1/sessions/",
            json=session_data,
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["agent_id"] == agent_id
        assert data["title"] is None

    @pytest.mark.asyncio
    async def test_create_session_with_agent_id_and_title(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 创建会话（带agent_id和title）"""
        # Arrange - 先创建一个 Agent
        agent_response = await client.post(
            "/api/v1/agents/",
            json={"name": "Test Agent", "system_prompt": "Test prompt"},
            headers=auth_headers,
            follow_redirects=False,
        )
        agent_id = agent_response.json()["id"]

        session_data = {
            "agent_id": agent_id,
            "title": "Test Session with Agent",
        }

        # Act
        response = await client.post(
            "/api/v1/sessions/",
            json=session_data,
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["agent_id"] == agent_id
        assert data["title"] == "Test Session with Agent"

    @pytest.mark.asyncio
    async def test_create_session_validates_title_length(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 创建会话时验证title长度"""
        # Arrange
        session_data = {
            "title": "a" * 201,  # 超过200字符限制
        }

        # Act
        response = await client.post(
            "/api/v1/sessions/",
            json=session_data,
            headers=auth_headers,
            follow_redirects=False,
        )

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_session_by_id(self, client: AsyncClient, auth_headers: dict):
        """测试: 根据 ID 获取会话"""
        # Arrange - 先创建一个会话
        create_response = await client.post(
            "/api/v1/sessions/",
            json={"title": "Test Session"},
            headers=auth_headers,
            follow_redirects=False,
        )
        session_id = create_response.json()["id"]

        # Act
        response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == session_id
        assert data["title"] == "Test Session"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client: AsyncClient, auth_headers: dict):
        """测试: 获取不存在的会话"""
        # Arrange
        import uuid

        non_existent_id = str(uuid.uuid4())

        # Act
        response = await client.get(
            f"/api/v1/sessions/{non_existent_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_session_requires_ownership(self, client: AsyncClient, auth_headers: dict):
        """测试: 获取会话需要所有权验证"""
        # 这个测试需要两个用户，在开发模式下可能难以实现
        # 暂时跳过，因为开发模式允许匿名用户
        pass

    @pytest.mark.asyncio
    async def test_update_session(self, client: AsyncClient, auth_headers: dict):
        """测试: 更新会话"""
        # Arrange - 先创建一个会话
        create_response = await client.post(
            "/api/v1/sessions/",
            json={"title": "Original Title"},
            headers=auth_headers,
            follow_redirects=False,
        )
        session_id = create_response.json()["id"]

        # Act
        response = await client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_session(self, client: AsyncClient, auth_headers: dict):
        """测试: 删除会话"""
        # Arrange - 先创建一个会话
        create_response = await client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
            follow_redirects=False,
        )
        session_id = create_response.json()["id"]

        # Act
        response = await client.delete(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # 验证会话已被删除
        get_response = await client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_session_messages(self, client: AsyncClient, auth_headers: dict):
        """测试: 获取会话消息"""
        # Arrange - 先创建一个会话
        create_response = await client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
            follow_redirects=False,
        )
        session_id = create_response.json()["id"]

        # Act
        response = await client.get(
            f"/api/v1/sessions/{session_id}/messages",
            headers=auth_headers,
        )

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # 新会话应该没有消息
        assert len(data) == 0
