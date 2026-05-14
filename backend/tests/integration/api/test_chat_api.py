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
            assert response.status_code == status.HTTP_200_OK, response.text
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
        """测试: 返回 SSE 流式响应。

        先 REST 创建会话再带 ``session_id`` 走流式，与同文件 ``test_chat_with_existing_session`` 一致，
        避免「流式响应期间再创建会话 + SAVEPOINT」与 fixture 单连接叠用时的 asyncpg teardown 竞态。
        """
        create_response = await client.post(
            "/api/v1/sessions/",
            json={"title": "SSE format check"},
            headers=auth_headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_id = create_response.json()["id"]

        # Act
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "session_id": session_id,
                "message": "Hello, please respond briefly",
            },
            headers=auth_headers,
        ) as response:
            # Assert
            assert response.status_code == status.HTTP_200_OK, response.text
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
        """测试: 使用已存在的会话进行对话（先 REST 创建会话，避免双段流式 + SAVEPOINT 下重复 commit 的 asyncpg 状态问题）"""
        create_response = await client.post(
            "/api/v1/sessions/",
            json={"title": "Integration chat preset"},
            headers=auth_headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_id = create_response.json()["id"]

        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "session_id": session_id,
                "message": "Message in existing session",
            },
            headers=auth_headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK, response.text
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type

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
        assert "session_created" not in event_types, "Should NOT create new session"

    @pytest.mark.asyncio
    async def test_chat_stream_does_not_use_request_scoped_chat_service_dependency(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """回归测试：SSE chat 不应复用 FastAPI 请求级 ChatUseCase/DB session。

        线上问题来自 ``StreamingResponse`` 期间复用请求依赖注入出来的 ``ChatUseCase``，
        其内部持有的 ``AsyncSession`` 会在流式响应边界与 FastAPI dependency teardown
        发生提交/关闭竞态。这里覆盖 ``get_chat_service`` 为必失败依赖：如果路由重新
        依赖它，本测试会失败；正确实现应在 SSE generator 内用独立 session 构造服务。
        """
        from bootstrap.main import app  # pylint: disable=import-outside-toplevel
        from libs.api.deps import get_chat_service  # pylint: disable=import-outside-toplevel

        create_response = await client.post(
            "/api/v1/sessions/",
            json={"title": "SSE session isolation"},
            headers=auth_headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_id = create_response.json()["id"]

        called = False

        async def fail_if_request_scoped_chat_service_is_used():
            nonlocal called
            called = True
            raise AssertionError("chat endpoint must build ChatUseCase inside SSE generator")

        app.dependency_overrides[get_chat_service] = fail_if_request_scoped_chat_service_is_used
        try:
            async with client.stream(
                "POST",
                "/api/v1/chat",
                json={
                    "session_id": session_id,
                    "message": "Check SSE session isolation",
                },
                headers=auth_headers,
            ) as response:
                assert response.status_code == status.HTTP_200_OK, response.text
                assert "text/event-stream" in response.headers.get("content-type", "")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        break
        finally:
            app.dependency_overrides.pop(get_chat_service, None)

        assert not called

    @pytest.mark.asyncio
    async def test_chat_invalid_model_ref_emits_error_event(
        self, client: AsyncClient, auth_headers: dict
    ):
        """非法 model_ref 应在 SSE 中下发 error 事件（不通过静默回退）"""
        create_response = await client.post(
            "/api/v1/sessions/",
            json={"title": "model ref invalid"},
            headers=auth_headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_id = create_response.json()["id"]

        errors: list[dict] = []
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "session_id": session_id,
                "message": "hi",
                "model_ref": "___not_in_catalog___/zzz-invalid-model-99999",
            },
            headers=auth_headers,
        ) as response:
            assert response.status_code == status.HTTP_200_OK, response.text
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_s = line[6:]
                    if data_s == "[DONE]":
                        break
                    try:
                        obj = json.loads(data_s)
                        if obj.get("type") == "error":
                            errors.append(obj)
                    except json.JSONDecodeError:
                        pass

        assert errors, "expected at least one error event in SSE"
        err_text = (errors[0].get("data") or {}).get("error", "")
        assert "模型不在可用列表中" in err_text
