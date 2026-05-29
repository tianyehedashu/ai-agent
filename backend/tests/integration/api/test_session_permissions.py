"""
Session API 权限测试

测试已认证用户之间的会话权限隔离，以及未认证访问被拒绝。
"""

from fastapi import status
from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestSessionPermissions:
    """会话权限测试"""

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access_registered_user_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 未认证用户不能访问注册用户的会话"""
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered User Session"},
            headers=auth_headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        session_id = create_response.json()["id"]

        anonymous_response = await dev_client.get(f"/api/v1/sessions/{session_id}")

        assert anonymous_response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_update_registered_user_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 未认证用户不能更新注册用户的会话"""
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        update_response = await dev_client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Hacked Title"},
        )

        assert update_response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_delete_registered_user_session(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 未认证用户不能删除注册用户的会话"""
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )
        session_id = create_response.json()["id"]

        delete_response = await dev_client.delete(f"/api/v1/sessions/{session_id}")

        assert delete_response.status_code == status.HTTP_401_UNAUTHORIZED

        get_response = await dev_client.get(
            f"/api/v1/sessions/{session_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_registered_user_session_response_format(
        self, dev_client: AsyncClient, auth_headers: dict
    ):
        """测试: 注册用户会话响应含 tenant_id"""
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Registered Session"},
            headers=auth_headers,
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        data = create_response.json()
        assert "id" in data
        assert "tenant_id" in data
        assert data["tenant_id"]
