"""
Chat API 集成测试

测试聊天 API 端点的完整功能
"""

from fastapi import status
from httpx import AsyncClient
import pytest

# Fixtures 从 conftest.py 自动导入


class TestChatAPI:
    """Chat API 集成测试"""

    @pytest.mark.asyncio
    async def test_chat_requires_authentication(self, client: AsyncClient):
        """测试: 需要认证"""
        # Act
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-session",
                "message": "Hello",
            },
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_chat_validates_request_body(self, client: AsyncClient, auth_headers: dict):
        """测试: 请求体验证"""
        # Act
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "",  # 空字符串
                "message": "Hello",
            },
            headers=auth_headers,
        )

        # Assert
        # 应该返回验证错误或 400
        assert response.status_code in [
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            status.HTTP_400_BAD_REQUEST,
        ]

    @pytest.mark.asyncio
    async def test_chat_creates_session_if_not_exists(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 不存在会话时创建会话"""
        # Act
        response = await client.post(
            "/api/v1/chat",
            json={
                "session_id": "new-session-123",
                "message": "Hello",
            },
            headers=auth_headers,
        )

        # Assert
        # 应该成功创建会话并返回响应
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_201_CREATED,
        ]

    @pytest.mark.asyncio
    async def test_chat_returns_sse_stream(self, client: AsyncClient, auth_headers: dict):
        """测试: 返回 SSE 流（如果支持）"""
        # Act
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "session_id": "test-session",
                "message": "Hello",
            },
            headers=auth_headers,
        ) as response:
            # Assert
            assert response.status_code == status.HTTP_200_OK
            # 如果是 SSE，应该有相应的 content-type
            content_type = response.headers.get("content-type", "")
            # 可能是 text/event-stream 或 application/json
            assert content_type != ""
