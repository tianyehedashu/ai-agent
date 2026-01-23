"""
Session API 权限测试

测试注册用户和匿名用户之间的会话权限隔离
"""

from fastapi import status
from httpx import AsyncClient
import pytest

from domains.identity.application import ANONYMOUS_USER_COOKIE


@pytest.mark.integration
class TestSessionPermissions:
    """会话权限测试"""

    @pytest.mark.asyncio
    async def test_anonymous_user_cannot_access_registered_user_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 匿名用户不能访问注册用户的会""
        # Arrange - 注册用户创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered User Session"},
            headers=auth_headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_id = create_response.json()["id"]

        # Act - 匿名用户（无认证头）尝试访问注册用户的会        # 清除可能存在的认证头，确保是匿名用户
        anonymous_response = await dev_client.get(f"/api/v1/sessions/{session_id}")

        # Assert - 应该返回 403 ?404（不泄露权限信息        assert anonymous_response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_registered_user_cannot_access_anonymous_user_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 注册用户不能访问匿名用户的会""
        # Arrange - 匿名用户创建会话
        # 清除认证头，确保是匿名用        anon_create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous User Session"},
        )
        assert anon_create_response.status_code == status.HTTP_201_CREATED
        anon_session_id = anon_create_response.json()["id"]

        # Act - 注册用户尝试访问匿名用户的会        registered_response = await dev_client.get(
            f"/api/v1/sessions/{anon_session_id}",
            headers=auth_headers,
        )

        # Assert - 应该返回 403 ?404（不泄露权限信息        assert registered_response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_anonymous_user_can_only_see_own_sessions(self, dev_client: AsyncClient):
        """测试: 匿名用户只能看到自己的会""
        # Arrange - 匿名用户 1 创建会话
        anon1_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anon1 Session"},
        )
        assert anon1_response.status_code == status.HTTP_201_CREATED
        anon1_session_id = anon1_response.json()["id"]
        anon1_cookie = dev_client.cookies.get(ANONYMOUS_USER_COOKIE)

        # Arrange - 匿名用户 2 创建会话（清Cookie 模拟新用户）
        dev_client.cookies.clear()
        anon2_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anon2 Session"},
        )
        assert anon2_response.status_code == status.HTTP_201_CREATED
        anon2_session_id = anon2_response.json()["id"]

        # Act - 匿名用户 1 查看自己的会话列        dev_client.cookies.set(ANONYMOUS_USER_COOKIE, anon1_cookie)
        anon1_list_response = await dev_client.get("/api/v1/sessions/")

        # Act - 匿名用户 2 查看自己的会话列        dev_client.cookies.clear()
        dev_client.cookies.set(
            ANONYMOUS_USER_COOKIE, anon2_response.cookies.get(ANONYMOUS_USER_COOKIE)
        )
        anon2_list_response = await dev_client.get("/api/v1/sessions/")

        # Assert
        assert anon1_list_response.status_code == status.HTTP_200_OK
        anon1_sessions = anon1_list_response.json()
        assert any(s["id"] == anon1_session_id for s in anon1_sessions)
        assert not any(s["id"] == anon2_session_id for s in anon1_sessions)

        assert anon2_list_response.status_code == status.HTTP_200_OK
        anon2_sessions = anon2_list_response.json()
        assert any(s["id"] == anon2_session_id for s in anon2_sessions)
        assert not any(s["id"] == anon1_session_id for s in anon2_sessions)

    @pytest.mark.asyncio
    async def test_anonymous_user_cannot_update_registered_user_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 匿名用户不能更新注册用户的会""
        # Arrange - 注册用户创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act - 匿名用户尝试更新
        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Hacked Title"},
        )

        # Assert
        assert update_response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

    @pytest.mark.asyncio
    async def test_anonymous_user_cannot_delete_registered_user_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 匿名用户不能删除注册用户的会""
        # Arrange - 注册用户创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        # Act - 匿名用户尝试删除
        delete_response = await dev_client.delete(f"/api/v1/sessions/{session_id}")

        # Assert
        assert delete_response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]

        # 验证会话仍然存在
        get_response = await dev_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_anonymous_user_session_response_format(self, dev_client: AsyncClient):
        """测试: 匿名用户会话的响应格式包anonymous_user_id"""
        # Arrange & Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous Session"},
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert "id" in data
        assert "user_id" in data
        assert "anonymous_user_id" in data
        assert data["user_id"] is None
        assert data["anonymous_user_id"] is not None
        assert isinstance(data["anonymous_user_id"], str)

    @pytest.mark.asyncio
    async def test_registered_user_session_response_format(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 注册用户会话的响应格式包user_id"""
        # Arrange & Act
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )

        # Assert
        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert "id" in data
        assert "user_id" in data
        assert "anonymous_user_id" in data
        assert data["user_id"] is not None
        assert data["anonymous_user_id"] is None

    @pytest.mark.asyncio
    async def test_anonymous_user_can_access_own_session_messages(self, dev_client: AsyncClient):
        """测试: 匿名用户可以访问自己会话的消""
        # Arrange - 创建匿名用户会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anonymous Session"},
        )
        session_id = create_response.json()["id"]

        # Act - 获取消息
        messages_response = await dev_client.get(f"/api/v1/sessions/{session_id}/messages")

        # Assert
        assert messages_response.status_code == status.HTTP_200_OK
        assert isinstance(messages_response.json(), list)

    @pytest.mark.asyncio
    async def test_anonymous_user_cannot_access_other_anonymous_user_messages(
        self, dev_client: AsyncClient
    ):
        """测试: 匿名用户不能访问其他匿名用户会话的消""
        # Arrange - 匿名用户 1 创建会话
        anon1_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Anon1 Session"},
        )
        anon1_session_id = anon1_response.json()["id"]

        # Arrange - 匿名用户 2（清Cookie?        dev_client.cookies.clear()

        # Act - 匿名用户 2 尝试访问匿名用户 1 的会话消        messages_response = await dev_client.get(f"/api/v1/sessions/{anon1_session_id}/messages")

        # Assert
        assert messages_response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ]
