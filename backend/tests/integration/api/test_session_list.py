"""
会话列表获取功能集成测试

测试获取用户会话列表的各种场景（分页、过滤、排序等）
"""

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestSessionList:
    """会话列表获取测试"""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 获取空会话列表"""
        # Act
        list_response = await dev_client.get("/api/v1/sessions/", headers=auth_headers)

        # Assert
        assert list_response.status_code == status.HTTP_200_OK
        sessions = list_response.json()
        assert isinstance(sessions, list)
        # 新用户可能没有会话，或者有默认会话

    @pytest.mark.asyncio
    async def test_list_sessions_with_pagination(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 分页获取会话列表"""
        # Arrange - 创建多个会话
        session_ids = []
        for i in range(5):
            create_response = await dev_client.post(
                "/api/v1/sessions/",
                json={"title": f"Session {i+1}"},
                headers=auth_headers,
            )
            session_ids.append(create_response.json()["id"])

        # Act - 第一页（limit=2）
        page1_response = await dev_client.get(
            "/api/v1/sessions/?skip=0&limit=2", headers=auth_headers
        )
        page1_sessions = page1_response.json()

        # Act - 第二页（limit=2）
        page2_response = await dev_client.get(
            "/api/v1/sessions/?skip=2&limit=2", headers=auth_headers
        )
        page2_sessions = page2_response.json()

        # Assert
        assert len(page1_sessions) <= 2
        assert len(page2_sessions) <= 2
        # 确保两页的会话不重复
        page1_ids = [s["id"] for s in page1_sessions]
        page2_ids = [s["id"] for s in page2_sessions]
        assert not set(page1_ids).intersection(set(page2_ids))

    @pytest.mark.asyncio
    async def test_list_sessions_with_agent_filter(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: ?agent_id 过滤会话列表"""
        # Arrange - 创建 Agent
        agent_response = await dev_client.post(
            "/api/v1/agents/",
            json={"name": "Filter Agent", "system_prompt": "Test"},
            headers=auth_headers,
        )
        agent_id = agent_response.json()["id"]

        # Arrange - 创建 Agent 的会话和不带 Agent 的会话
        with_agent_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"agent_id": agent_id, "title": "With Agent"},
            headers=auth_headers,
        )
        with_agent_id = with_agent_response.json()["id"]

        without_agent_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Without Agent"},
            headers=auth_headers,
        )
        without_agent_id = without_agent_response.json()["id"]

        # Act - ?agent_id 过滤
        filtered_response = await dev_client.get(
            f"/api/v1/sessions/?agent_id={agent_id}", headers=auth_headers
        )
        filtered_sessions = filtered_response.json()

        # Assert
        assert filtered_response.status_code == status.HTTP_200_OK
        filtered_ids = [s["id"] for s in filtered_sessions]
        assert with_agent_id in filtered_ids
        assert without_agent_id not in filtered_ids

    @pytest.mark.asyncio
    async def test_list_sessions_limit_validation(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: limit 参数验证"""
        # Act - limit 超过最大值（100）
        response = await dev_client.get("/api/v1/sessions/?limit=101", headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_list_sessions_skip_validation(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: skip 参数验证"""
        # Act - skip 为负数
        response = await dev_client.get("/api/v1/sessions/?skip=-1", headers=auth_headers)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_list_sessions_response_format(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 会话列表响应格式"""
        # Arrange - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Format Test Session"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201

        # Act
        list_response = await dev_client.get("/api/v1/sessions/", headers=auth_headers)
        sessions = list_response.json()

        # Assert - 验证响应格式
        assert isinstance(sessions, list)
        if sessions:
            session = sessions[0]
            required_fields = [
                "id",
                "user_id",
                "anonymous_user_id",
                "agent_id",
                "title",
                "status",
                "message_count",
                "token_count",
                "created_at",
                "updated_at",
            ]
            for field in required_fields:
                assert field in session, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_list_anonymous_user_sessions(self, dev_client: AsyncClient):
        """测试: 匿名用户获取会话列表"""
        # Arrange - 创建匿名用户会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous Session"},
        )
        anon_session_id = create_response.json()["id"]

        # Act
        list_response = await dev_client.get("/api/v1/sessions/")
        sessions = list_response.json()

        # Assert
        assert list_response.status_code == status.HTTP_200_OK
        assert isinstance(sessions, list)
        # 应该包含刚创建的会话
        session_ids = [s["id"] for s in sessions]
        assert anon_session_id in session_ids
        # 验证所有会话都属于匿名用户
        for session in sessions:
            assert session["user_id"] is None
            assert session["anonymous_user_id"] is not None

    @pytest.mark.asyncio
    async def test_list_sessions_only_returns_own_sessions(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 用户只能看到自己的会话"""
        # Arrange - 注册用户创建会话
        registered_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )
        registered_session_id = registered_response.json()["id"]

        # Arrange - 匿名用户创建会话
        anonymous_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous Session"},
        )
        anonymous_session_id = anonymous_response.json()["id"]

        # Act - 注册用户获取会话列表
        registered_list = await dev_client.get("/api/v1/sessions/", headers=auth_headers)
        registered_sessions = registered_list.json()

        # Act - 匿名用户获取会话列表
        anonymous_list = await dev_client.get("/api/v1/sessions/")
        anonymous_sessions = anonymous_list.json()

        # Assert - 注册用户只能看到自己的会话
        registered_ids = [s["id"] for s in registered_sessions]
        assert registered_session_id in registered_ids
        assert anonymous_session_id not in registered_ids

        # Assert - 匿名用户只能看到自己的会话
        anonymous_ids = [s["id"] for s in anonymous_sessions]
        assert anonymous_session_id in anonymous_ids
        assert registered_session_id not in anonymous_ids
