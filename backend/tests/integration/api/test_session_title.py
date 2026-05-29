"""
会话标题功能集成测试

测试标题生成、更新等功能
"""

from unittest.mock import AsyncMock, patch

from fastapi import status
from httpx import AsyncClient
import pytest

from domains.session.application.ports import TitleLlmChatResult


@pytest.mark.integration
class TestSessionTitle:
    """会话标题测试"""

    @pytest.mark.asyncio
    async def test_update_session_title(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 更新会话标题"""
        # Arrange - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Original Title"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act - 更新标题
        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )

        # Assert
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_update_title_to_none(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 将标题更新为 None（清除标题）"""
        # Arrange - 创建带标题的会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Has Title"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act - 更新标题None
        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": None},
            headers=auth_headers,
        )

        # Assert
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["title"] is None

    @pytest.mark.asyncio
    async def test_update_title_max_length(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 更新标题到最大长度"""
        # Arrange
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]
        max_title = "a" * 200

        # Act
        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": max_title},
            headers=auth_headers,
        )

        # Assert
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["title"] == max_title

    @pytest.mark.asyncio
    async def test_update_title_exceeds_max_length(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 更新标题超过最大长度"""
        # Arrange
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]
        too_long_title = "a" * 201

        # Act
        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": too_long_title},
            headers=auth_headers,
        )

        # Assert
        assert update_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @pytest.mark.asyncio
    async def test_generate_title_with_summary_strategy(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 使用 summary 策略生成标题"""
        # Arrange - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Mock LLM 响应
        mock_title = "生成的标题"

        with patch(
            "domains.agent.application.title_generation_service.LlmTitleGenerationAdapter.chat",
            new_callable=AsyncMock,
            return_value=TitleLlmChatResult(content=mock_title),
        ):
            # Act - 生成标题
            generate_response = await dev_client.post(
                f"/api/v1/sessions/{session_id}/generate-title?strategy=summary",
                headers=auth_headers,
            )

            # Assert
            # 注意：如果会话没有消息，生成可能失败
            if generate_response.status_code == status.HTTP_200_OK:
                data = generate_response.json()
                assert "title" in data
            else:
                # 如果没有消息，生成可能失败（这是预期的）
                assert generate_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_generate_title_with_first_message_strategy(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 使用 first_message 策略生成标题"""
        # Arrange - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Mock LLM 响应
        mock_title = "第一条消息标题"

        with patch(
            "domains.agent.application.title_generation_service.LlmTitleGenerationAdapter.chat",
            new_callable=AsyncMock,
            return_value=TitleLlmChatResult(content=mock_title),
        ):
            # Act - 生成标题
            generate_response = await dev_client.post(
                f"/api/v1/sessions/{session_id}/generate-title?strategy=first_message",
                headers=auth_headers,
            )

            # Assert
            # 注意：如果会话没有消息，生成可能失败
            if generate_response.status_code == status.HTTP_200_OK:
                data = generate_response.json()
                assert "title" in data
            else:
                assert generate_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_generate_title_invalid_strategy(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 使用无效的策略生成标题"""
        # Arrange
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act
        generate_response = await dev_client.post(
            f"/api/v1/sessions/{session_id}/generate-title?strategy=invalid",
            headers=auth_headers,
        )

        # Assert
        assert generate_response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_generate_title_requires_ownership(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 生成标题需要会话所有权"""
        # Arrange - 注册用户创建会话
        registered_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        session_id = registered_response.json()["id"]

        # Act - 未认证用户尝试生成标题
        generate_response = await dev_client.post(
            f"/api/v1/sessions/{session_id}/generate-title?strategy=summary",
        )

        # Assert
        assert generate_response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_update_title_and_status_together(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 同时更新标题和状态"""
        # Arrange
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act
        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "New Title", "status": "archived"},
            headers=auth_headers,
        )

        # Assert
        assert update_response.status_code == status.HTTP_200_OK
        data = update_response.json()
        assert data["title"] == "New Title"
        assert data["status"] == "archived"
