"""
Video Task API 集成测试

测试视频任务创建、会话所有权校验等。
"""

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestVideoTaskCreateSessionOwnership:
    """视频任务创建时的会话所有权校验"""

    @pytest.mark.asyncio
    async def test_create_video_task_with_other_user_session_returns_403(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """带 session_id 且会话属于其他用户时，应返回 403"""
        # Arrange - 注册用户创建会话
        create_session_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered User Session"},
            headers=auth_headers,
        )
        assert create_session_response.status_code == status.HTTP_201_CREATED
        session_id = create_session_response.json()["id"]

        # Act - 匿名用户尝试用该 session_id 创建视频任务（无认证头）
        create_task_response = await dev_client.post(
            "/api/v1/video-tasks/",
            json={
                "session_id": session_id,
                "prompt_text": "test prompt",
            },
        )

        # Assert - 应返回 403 或 404（无权使用该会话，不泄露权限信息）
        assert create_task_response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_create_video_task_with_own_session_succeeds(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """带 session_id 且会话属于当前用户时，应创建成功"""
        # Arrange - 注册用户创建会话
        create_session_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "My Session"},
            headers=auth_headers,
        )
        assert create_session_response.status_code == status.HTTP_201_CREATED
        session_id = create_session_response.json()["id"]

        # Act - 同一用户用该 session_id 创建视频任务
        create_task_response = await dev_client.post(
            "/api/v1/video-tasks/",
            json={
                "session_id": session_id,
                "prompt_text": "test prompt",
            },
            headers=auth_headers,
        )

        # Assert
        assert create_task_response.status_code == status.HTTP_201_CREATED
        data = create_task_response.json()
        assert data["session_id"] == session_id
        assert data["prompt_text"] == "test prompt"
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_video_task_updates_session_title_when_empty(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """已有会话无标题时创建视频任务，应将会话标题设为 prompt 前 50 字"""
        # Arrange - 创建无标题会话
        create_session_response = await dev_client.post(
            "/api/v1/sessions/",
            json={},
            headers=auth_headers,
        )
        assert create_session_response.status_code == status.HTTP_201_CREATED
        session_id = create_session_response.json()["id"]
        assert create_session_response.json().get("title") is None

        prompt_text = "A beautiful product video for my new gadget that shows all features"
        # Act - 用该会话创建视频任务
        create_task_response = await dev_client.post(
            "/api/v1/video-tasks/",
            json={
                "session_id": session_id,
                "prompt_text": prompt_text,
            },
            headers=auth_headers,
        )
        assert create_task_response.status_code == status.HTTP_201_CREATED

        # Assert - 会话标题应被更新为 prompt 前 50 字
        get_session_response = await dev_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_session_response.status_code == status.HTTP_200_OK
        session_data = get_session_response.json()
        expected_title = prompt_text[:50] + "..."
        assert session_data["title"] == expected_title
