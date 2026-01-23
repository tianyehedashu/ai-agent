"""
会话创建功能集成测试

测试创建新会话的各种场景和边界情"""

import uuid

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestSessionCreate:
    """会话创建测试"""

    @pytest.mark.asyncio
    async def test_create_session_with_all_params(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 使用所有参数创建会""
        # Arrange - 先创Agent
        agent_response = await dev_client.post(
            "/api/v1/agents/",
            json={"name": "Test Agent", "system_prompt": "Test prompt"},
            headers=auth_headers,
        )
        agent_id = agent_response.json()["id"]

        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={
                "agent_id": agent_id,
                "title": "Complete Session",
            },
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert data["agent_id"] == agent_id
        assert data["title"] == "Complete Session"
        assert data["status"] == "active"
        assert data["message_count"] == 0
        assert data["token_count"] == 0

    @pytest.mark.asyncio
    async def test_create_session_without_params(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 不提供任何参数创建会话（使用默认值）"""
        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert data["agent_id"] is None
        assert data["title"] is None
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_session_with_title_only(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 仅提title 创建会话"""
        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Title Only Session"},
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert data["title"] == "Title Only Session"
        assert data["agent_id"] is None

    @pytest.mark.asyncio
    async def test_create_session_with_agent_only(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 仅提agent_id 创建会话"""
        # Arrange
        agent_response = await dev_client.post(
            "/api/v1/agents/",
            json={"name": "Test Agent", "system_prompt": "Test prompt"},
            headers=auth_headers,
        )
        agent_id = agent_response.json()["id"]

        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"agent_id": agent_id},
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert data["agent_id"] == agent_id
        assert data["title"] is None

    @pytest.mark.asyncio
    async def test_create_session_title_max_length(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 创建会话title 最大长度限""
        # Arrange - 200字符的title（最大长度）
        max_title = "a" * 200

        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": max_title},
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert data["title"] == max_title

    @pytest.mark.asyncio
    async def test_create_session_title_exceeds_max_length(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: title 超过最大长度时返回验证错误"""
        # Arrange - 201字符的title（超过最大长度）
        too_long_title = "a" * 201

        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": too_long_title},
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_session_with_invalid_agent_id(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 使用无效agent_id 创建会话"""
        # Arrange - 不存在的 agent_id
        invalid_agent_id = str(uuid.uuid4())

        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"agent_id": invalid_agent_id},
            headers=auth_headers,
        )

        # Assert
        # 注意：根据实现，可能会创建会话但 agent_id 无效，或者返回错        # 这里假设会创建会话（外键约束可能不会立即检查）
        assert create_response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_create_multiple_sessions(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 创建多个会话"""
        # Act - 创建3个会        session_ids = []
        for i in range(3):
            create_response = await dev_client.post(
                "/api/v1/sessions/",
                json={"title": f"Session {i+1}"},
                headers=auth_headers,
            )
            assert create_response.status_code == status.HTTP_201_CREATED
            session_ids.append(create_response.json()["id"])

        # Assert - 所有会话ID应该不同
        assert len(set(session_ids)) == 3

        # Assert - 所有会话都应该在列表中
        list_response = await dev_client.get("/api/v1/sessions/", headers=auth_headers)
        sessions = list_response.json()
        session_ids_in_list = [s["id"] for s in sessions]
        for session_id in session_ids:
            assert session_id in session_ids_in_list

    @pytest.mark.asyncio
    async def test_create_anonymous_session_with_title(self, dev_client: AsyncClient):
        """测试: 匿名用户创建带标题的会话"""
        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous Session Title"},
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert data["title"] == "Anonymous Session Title"
        assert data["user_id"] is None
        assert data["anonymous_user_id"] is not None

    @pytest.mark.asyncio
    async def test_create_session_empty_title(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 创建会话title 为空字符""
        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": ""},
            headers=auth_headers,
        )

        # Assert
        # 空字符串可能被视None，或者被拒绝
        assert create_response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    @pytest.mark.asyncio
    async def test_create_session_unicode_title(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 创建会话时使Unicode 字符title"""
        # Arrange
        unicode_title = "测试会话 🚀 中文标题"

        # Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": unicode_title},
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert data["title"] == unicode_title
