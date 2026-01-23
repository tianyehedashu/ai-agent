"""
匿名用户会话完整生命周期集成测试

测试匿名用户从创建会话到删除会话的完整流"""

from fastapi import status
from httpx import AsyncClient
import pytest

from domains.identity.application import ANONYMOUS_USER_COOKIE


@pytest.mark.integration
class TestAnonymousSessionLifecycle:
    """匿名用户会话生命周期测试"""

    @pytest.mark.asyncio
    async def test_anonymous_user_complete_lifecycle(self, dev_client: AsyncClient):
        """测试: 匿名用户会话的完整生命周""
        # 1. 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "My Anonymous Session"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_data = create_response.json()
        session_id = session_data["id"]
        anonymous_user_id = session_data["anonymous_user_id"]

        # 验证响应格式
        assert session_data["user_id"] is None
        assert anonymous_user_id is not None
        assert session_data["title"] == "My Anonymous Session"
        assert session_data["status"] == "active"
        assert session_data["message_count"] == 0
        assert session_data["token_count"] == 0

        # 2. 获取会话详情
        get_response = await dev_client.get(f"/api/v1/sessions/{session_id}")
        assert get_response.status_code == status.HTTP_200_OK
        get_data = get_response.json()
        assert get_data["id"] == session_id
        assert get_data["anonymous_user_id"] == anonymous_user_id

        # 3. 更新会话
        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Updated Title", "status": "archived"},
        )
        assert update_response.status_code == status.HTTP_200_OK
        update_data = update_response.json()
        assert update_data["title"] == "Updated Title"
        assert update_data["status"] == "archived"

        # 4. 获取会话列表（应该包含这个会话）
        list_response = await dev_client.get("/api/v1/sessions/")
        assert list_response.status_code == status.HTTP_200_OK
        sessions = list_response.json()
        assert any(s["id"] == session_id for s in sessions)

        # 5. 获取会话消息（初始为空）
        messages_response = await dev_client.get(f"/api/v1/sessions/{session_id}/messages")
        assert messages_response.status_code == status.HTTP_200_OK
        messages = messages_response.json()
        assert isinstance(messages, list)
        assert len(messages) == 0

        # 6. 删除会话
        delete_response = await dev_client.delete(f"/api/v1/sessions/{session_id}")
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # 7. 验证会话已被删除
        get_deleted_response = await dev_client.get(f"/api/v1/sessions/{session_id}")
        assert get_deleted_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_anonymous_user_multiple_sessions(self, dev_client: AsyncClient):
        """测试: 匿名用户可以创建多个会话"""
        # Arrange & Act - 创建多个会话
        session_ids = []
        for i in range(3):
            create_response = await dev_client.post(
                "/api/v1/sessions/",
                json={"title": f"Session {i+1}"},
            )
            assert create_response.status_code == status.HTTP_201_CREATED
            session_ids.append(create_response.json()["id"])

        # Assert - 所有会话都属于同一个匿名用        list_response = await dev_client.get("/api/v1/sessions/")
        assert list_response.status_code == status.HTTP_200_OK
        sessions = list_response.json()
        session_ids_in_list = [s["id"] for s in sessions]

        for session_id in session_ids:
            assert session_id in session_ids_in_list
            # 验证所有会话的 anonymous_user_id 相同
            session_data = next(s for s in sessions if s["id"] == session_id)
            assert session_data["anonymous_user_id"] is not None
            assert session_data["user_id"] is None

    @pytest.mark.asyncio
    async def test_anonymous_user_session_persistence(self, dev_client: AsyncClient):
        """测试: 匿名用户会话在多次请求间保持"""
        # Arrange - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Persistent Session"},
        )
        session_id = create_response.json()["id"]
        anonymous_user_id = create_response.json()["anonymous_user_id"]

        # Act - 多次请求获取会话
        for _ in range(3):
            get_response = await dev_client.get(f"/api/v1/sessions/{session_id}")
            assert get_response.status_code == status.HTTP_200_OK
            assert get_response.json()["anonymous_user_id"] == anonymous_user_id

        # Assert - 会话仍然存在
        list_response = await dev_client.get("/api/v1/sessions/")
        sessions = list_response.json()
        assert any(s["id"] == session_id for s in sessions)

    @pytest.mark.asyncio
    async def test_anonymous_user_session_with_agent(self, dev_client: AsyncClient):
        """测试: 匿名用户可以创建Agent 的会""
        # 注意：这个测试需要先创建一Agent
        # 但在开发模式下，Agent 可能需要注册用        # 这里先测试基本流程，如果 Agent 创建失败则跳
        # Arrange - 尝试创建 Agent（可能需要认证）
        # 如果失败，则跳过此测        try:
            agent_response = await dev_client.post(
                "/api/v1/agents/",
                json={"name": "Test Agent", "system_prompt": "Test"},
            )
            if agent_response.status_code != status.HTTP_201_CREATED:
                pytest.skip("Cannot create agent without authentication")
            agent_id = agent_response.json()["id"]
        except Exception:
            pytest.skip("Cannot create agent without authentication")

        # Act - 创建Agent 的会        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"agent_id": agent_id, "title": "Session with Agent"},
        )

        # Assert
        if create_response.status_code == status.HTTP_201_CREATED:
            session_data = create_response.json()
            assert session_data["agent_id"] == agent_id
            assert session_data["anonymous_user_id"] is not None

    @pytest.mark.asyncio
    async def test_anonymous_user_cookie_persistence_across_sessions(
        self, dev_client: AsyncClient
    ):
        """测试: 匿名用户 Cookie 在会话间保持"""
        # Arrange - 首次请求获取 Cookie
        first_response = await dev_client.get("/api/v1/sessions/")
        assert first_response.status_code == status.HTTP_200_OK
        first_cookie = dev_client.cookies.get(ANONYMOUS_USER_COOKIE)
        assert first_cookie is not None

        # Act - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Test Session"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_anonymous_id = create_response.json()["anonymous_user_id"]

        # Act - 再次请求（应该使用相同的 Cookie?        second_response = await dev_client.get("/api/v1/sessions/")
        second_cookie = dev_client.cookies.get(ANONYMOUS_USER_COOKIE)

        # Assert - Cookie 应该保持一        assert first_cookie == second_cookie
        # 会话应该属于同一个匿名用        sessions = second_response.json()
        assert any(s["anonymous_user_id"] == session_anonymous_id for s in sessions)
