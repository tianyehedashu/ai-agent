"""
Token 过期处理集成测试

测试 JWT token 过期/无效时的行为：
1. 过期 token 返回 401（不再静默降级）
2. 有效 token 正常访问
3. 无 token 走匿名流程（开发模式）
"""

from httpx import AsyncClient
import pytest


@pytest.mark.integration
class TestTokenExpiry:
    """Token 过期处理集成测试

    验证当 JWT token 过期或无效时，后端统一返回 401。
    前端根据 401 清除过期 token，用户需重新登录。
    """

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, dev_client: AsyncClient):
        """测试: 无效 token 返回 401"""
        headers = {"Authorization": "Bearer invalid-expired-token-abc123"}

        response = await dev_client.get("/api/v1/sessions/", headers=headers)

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_no_degraded_header_on_401(self, dev_client: AsyncClient):
        """测试: 401 响应不再包含 X-Token-Degraded 头"""
        headers = {"Authorization": "Bearer expired-token-xyz"}

        response = await dev_client.get("/api/v1/sessions/", headers=headers)

        assert response.status_code == 401
        assert response.headers.get("x-token-degraded") is None

    @pytest.mark.asyncio
    async def test_valid_token_returns_200(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """测试: 有效 token 正常访问"""
        response = await dev_client.get("/api/v1/sessions/", headers=auth_headers)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_no_token_anonymous_access(self, dev_client: AsyncClient):
        """测试: 无 token 走匿名流程（开发模式），正常返回 200"""
        response = await dev_client.get("/api/v1/sessions/")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_user_data_stays_accessible_after_relogin(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """测试: 用户创建数据后 token 过期，重新登录仍可访问

        核心场景：
        1. 有效 token 创建会话
        2. Token 过期 → 401（非降级）
        3. 重新登录（同一 token）→ 仍可看到会话
        """
        # Step 1: 有效 token 创建会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Leo's session"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201

        # Step 2: 无效 token → 401
        expired_response = await dev_client.get(
            "/api/v1/sessions/",
            headers={"Authorization": "Bearer expired-token"},
        )
        assert expired_response.status_code == 401

        # Step 3: 重新登录（用有效 token）→ 仍然能看到数据
        list_response = await dev_client.get("/api/v1/sessions/", headers=auth_headers)
        assert list_response.status_code == 200
        sessions = list_response.json()
        assert any(s["title"] == "Leo's session" for s in sessions)
