"""
Token 续期集成测试

验证 /token（增强登录）和 /token/refresh 端点的完整流程：
1. 登录返回 access_token + refresh_token
2. refresh_token 可换取新 token pair
3. 新 access_token 可正常访问受保护接口
"""

import uuid

from fastapi_users.password import PasswordHelper
from httpx import AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.infrastructure.models.user import User

_pwd = PasswordHelper()


@pytest_asyncio.fixture
async def login_user(db_session: AsyncSession) -> tuple[User, str]:
    """可登录的测试用户（有正确的密码哈希）"""
    password = "testpassword123"
    user = User(
        email=f"login_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=_pwd.hash(password),
        name="Login Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user, password


@pytest.mark.integration
class TestTokenEndpoint:
    """POST /api/v1/auth/token - 增强登录端点"""

    @pytest.mark.asyncio
    async def test_login_returns_token_pair(
        self, dev_client: AsyncClient, login_user: tuple[User, str]
    ):
        """登录成功应返回完整 token pair"""
        user, password = login_user

        response = await dev_client.post(
            "/api/v1/auth/token",
            json={"email": user.email, "password": password},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_invalid_password(
        self, dev_client: AsyncClient, login_user: tuple[User, str]
    ):
        """错误密码应返回 401"""
        user, _ = login_user

        response = await dev_client.post(
            "/api/v1/auth/token",
            json={"email": user.email, "password": "wrong-password"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, dev_client: AsyncClient):
        """不存在的用户应返回 401"""
        response = await dev_client.post(
            "/api/v1/auth/token",
            json={"email": "nobody@example.com", "password": "whatever"},
        )

        assert response.status_code == 401


@pytest.mark.integration
class TestRefreshEndpoint:
    """POST /api/v1/auth/token/refresh - Token 续期端点"""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_token_pair(
        self, dev_client: AsyncClient, login_user: tuple[User, str]
    ):
        """有效 refresh_token 应返回新的 token pair"""
        user, password = login_user

        # Step 1: 登录获取 token pair
        login_resp = await dev_client.post(
            "/api/v1/auth/token",
            json={"email": user.email, "password": password},
        )
        tokens = login_resp.json()

        # Step 2: 用 refresh_token 续期
        refresh_resp = await dev_client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert refresh_resp.status_code == 200
        new_tokens = refresh_resp.json()
        assert new_tokens["access_token"]
        assert new_tokens["refresh_token"]
        assert new_tokens["token_type"] == "bearer"
        assert new_tokens["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_returns_401(self, dev_client: AsyncClient):
        """无效 refresh_token 应返回 401"""
        response = await dev_client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": "invalid-token-abc123"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_new_access_token_authenticates(
        self, dev_client: AsyncClient, login_user: tuple[User, str]
    ):
        """续期后的新 access_token 应能正常访问受保护接口"""
        user, password = login_user

        # 登录 → 续期 → 使用新 token
        login_resp = await dev_client.post(
            "/api/v1/auth/token",
            json={"email": user.email, "password": password},
        )
        tokens = login_resp.json()

        refresh_resp = await dev_client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        new_tokens = refresh_resp.json()

        # 用新 access_token 访问 /auth/me
        me_resp = await dev_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
        )

        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["email"] == user.email
        assert me_data["is_anonymous"] is False
