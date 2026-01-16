"""
Chat API 集成测试

测试聊天 API 端点的完整功能，包括：
1. 认证和验证
2. SSE 流式响应
3. 会话创建和管理
4. 多轮对话
"""

import json

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
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_400_BAD_REQUEST,
        ]

    @pytest.mark.asyncio
    async def test_chat_creates_session_if_not_exists(
        self, client: AsyncClient, auth_headers: dict
    ):
        """测试: 不存在会话时创建会话"""
        # Act
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "message": "Hello, this is a test message",
            },
            headers=auth_headers,
        ) as response:
            # Assert
            assert response.status_code == status.HTTP_200_OK
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

            # 读取 SSE 事件
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # 移除 "data: " 前缀
                    if data_str == "[DONE]":
                        break
                    try:
                        event_data = json.loads(data_str)
                        events.append(event_data)
                    except json.JSONDecodeError:
                        pass

            # 验证至少收到了 session_created 事件
            session_created = any(event.get("type") == "session_created" for event in events)
            assert session_created, "Should receive session_created event"

    @pytest.mark.asyncio
    async def test_chat_returns_sse_stream(self, client: AsyncClient, auth_headers: dict):
        """测试: 返回 SSE 流式响应"""
        # Act
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "message": "Hello, please respond briefly",
            },
            headers=auth_headers,
        ) as response:
            # Assert
            assert response.status_code == status.HTTP_200_OK
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

            # 验证 SSE 事件格式
            event_count = 0
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    event_count += 1
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    # 验证事件数据是有效的 JSON
                    try:
                        event_data = json.loads(data_str)
                        assert "type" in event_data
                    except json.JSONDecodeError:
                        pytest.fail(f"Invalid JSON in SSE event: {data_str}")

            # 应该至少收到一些事件
            assert event_count > 0, "Should receive at least one SSE event"

    @pytest.mark.asyncio
    async def test_chat_with_existing_session(self, client: AsyncClient, auth_headers: dict):
        """测试: 使用已存在的会话进行对话"""
        # 先创建一个会话
        session_id = None
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "message": "First message",
            },
            headers=auth_headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        event_data = json.loads(data_str)
                        if event_data.get("type") == "session_created":
                            session_id = event_data.get("data", {}).get("session_id")
                            break
                    except json.JSONDecodeError:
                        pass

        # 必须获取到 session_id
        assert session_id is not None, "Should receive session_id from session_created event"

        # 使用已存在的会话发送第二条消息
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "session_id": session_id,
                "message": "Second message",
            },
            headers=auth_headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

            # 验证第二条消息不会再收到 session_created 事件
            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        event_data = json.loads(data_str)
                        events.append(event_data)
                    except json.JSONDecodeError:
                        pass

            event_types = [e.get("type") for e in events]
            # 已有会话不应该再创建新会话
            assert "session_created" not in event_types, "Should NOT create new session"
