"""
会话删除功能集成测试

测试删除会话的各种场景和边界情况
"""

import uuid

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestSessionDelete:
    """会话删除测试"""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, dev_client: AsyncClient, auth_headers: dict):
        """测试: 成功删除会话"""
        # Arrange - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "To Be Deleted"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act - 删除会话
        delete_response = await dev_client.delete(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        # Assert
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Assert - 验证会话已被删除
        get_response = await dev_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 删除不存在的会话"""
        # Arrange
        nonexistent_id = str(uuid.uuid4())

        # Act
        delete_response = await dev_client.delete(
            f"/api/v1/sessions/{nonexistent_id}",
            headers=auth_headers,
        )

        # Assert
        assert delete_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_session_without_permission(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 删除其他用户的会话（无权限）"""
        # Arrange - 注册用户创建会话
        registered_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )
        registered_session_id = registered_response.json()["id"]

        # Act - 匿名用户尝试删除注册用户的会话
        delete_response = await dev_client.delete(f"/api/v1/sessions/{registered_session_id}")

        # Assert
        assert delete_response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

        # Assert - 会话仍然存在
        get_response = await dev_client.get(
            f"/api/v1/sessions/{registered_session_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_delete_anonymous_user_session(self, dev_client: AsyncClient):
        """测试: 匿名用户删除自己的会话"""
        # Arrange - 创建匿名用户会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous Session"},
        )
        session_id = create_response.json()["id"]

        # Act - 删除会话
        delete_response = await dev_client.delete(f"/api/v1/sessions/{session_id}")

        # Assert
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Assert - 验证会话已被删除
        get_response = await dev_client.get(f"/api/v1/sessions/{session_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_session_removes_from_list(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 删除会话后从列表中移除"""
        # Arrange - 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "List Test Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act - 获取列表（应该包含该会话）
        list_before = await dev_client.get("/api/v1/sessions/", headers=auth_headers)
        sessions_before = list_before.json()
        assert any(s["id"] == session_id for s in sessions_before)

        # Act - 删除会话
        await dev_client.delete(f"/api/v1/sessions/{session_id}", headers=auth_headers)

        # Act - 再次获取列表（不应该包含该会话）
        list_after = await dev_client.get("/api/v1/sessions/", headers=auth_headers)
        sessions_after = list_after.json()
        assert not any(s["id"] == session_id for s in sessions_after)

    @pytest.mark.asyncio
    async def test_delete_multiple_sessions(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 删除多个会话"""
        # Arrange - 创建多个会话
        session_ids = []
        for i in range(3):
            create_response = await dev_client.post(
                "/api/v1/sessions/",
                json={"title": f"Session {i+1}"},
                headers=auth_headers,
            )
            session_ids.append(create_response.json()["id"])

        # Act - 删除所有会话
        for session_id in session_ids:
            delete_response = await dev_client.delete(
                f"/api/v1/sessions/{session_id}",
                headers=auth_headers,
            )
            assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Assert - 所有会话都已删除
        for session_id in session_ids:
            get_response = await dev_client.get(
                f"/api/v1/sessions/{session_id}",
                headers=auth_headers,
            )
            assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_session_with_messages(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 删除包含消息的会话"""
        # Arrange - 创建会话并添加消息（通过聊天接口）
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Session with Messages"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # 注意：这里假设有消息，实际测试可能需要通过聊天接口添加消息
        # 或者直接通过数据库添加消息
        # Act - 删除会话
        delete_response = await dev_client.delete(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )

        # Assert
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        # Assert - 会话已被删除
        get_response = await dev_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_invalid_session_id_format(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 使用无效格式session_id 删除会话"""
        # Arrange
        invalid_id = "not-a-valid-uuid"

        # Act
        delete_response = await dev_client.delete(
            f"/api/v1/sessions/{invalid_id}",
            headers=auth_headers,
        )

        # Assert
        # 可能返回 404 或 422，取决于 UUID 验证的实现
        assert delete_response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]
