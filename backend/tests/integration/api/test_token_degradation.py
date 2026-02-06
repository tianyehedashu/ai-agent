"""
Token 降级机制集成测试

测试开发模式下 JWT token 过期时的静默降级行为：
1. 过期/无效 token 降级为匿名用户
2. 响应头包含 X-Token-Degraded 标志
3. 有效 token 不触发降级
4. 降级后数据按匿名用户隔离（而非按原用户）
"""

import re

from httpx import AsyncClient
import pytest

from domains.identity.presentation.deps import ANONYMOUS_USER_COOKIE


@pytest.mark.integration
class TestTokenDegradation:
    """Token 降级机制集成测试

    验证开发模式下，当 JWT token 过期或无效时：
    - 后端静默降级为匿名用户（不返回 401）
    - 响应头 X-Token-Degraded: true 通知前端
    """

    @pytest.mark.asyncio
    async def test_invalid_token_returns_degraded_header(self, dev_client: AsyncClient):
        """测试: 无效 token 触发降级，响应头包含 X-Token-Degraded"""
        # Arrange - 使用无效的 JWT token
        headers = {"Authorization": "Bearer invalid-expired-token-abc123"}

        # Act
        response = await dev_client.get("/api/v1/sessions/", headers=headers)

        # Assert
        assert response.status_code == 200  # 开发模式不返回 401
        assert response.headers.get("x-token-degraded") == "true"

    @pytest.mark.asyncio
    async def test_valid_token_no_degraded_header(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """测试: 有效 token 不触发降级"""
        # Act - 使用有效 token
        response = await dev_client.get("/api/v1/sessions/", headers=auth_headers)

        # Assert
        assert response.status_code == 200
        assert response.headers.get("x-token-degraded") is None

    @pytest.mark.asyncio
    async def test_no_token_no_degraded_header(self, dev_client: AsyncClient):
        """测试: 无 token 的匿名访问不触发降级（这是正常的匿名流程）"""
        # Act - 不带任何 token
        response = await dev_client.get("/api/v1/sessions/")

        # Assert
        assert response.status_code == 200
        # 正常匿名访问不会设置降级头，降级头仅在 "有 token 但无效" 时设置
        assert response.headers.get("x-token-degraded") is None

    @pytest.mark.asyncio
    async def test_degraded_request_gets_anonymous_cookie(self, dev_client: AsyncClient):
        """测试: 降级后设置匿名用户 Cookie"""
        # Arrange - 使用无效 token
        headers = {"Authorization": "Bearer expired-token-xyz"}

        # Act
        response = await dev_client.get("/api/v1/sessions/", headers=headers)

        # Assert - 应同时收到降级标志和匿名 Cookie
        assert response.headers.get("x-token-degraded") == "true"
        set_cookie = response.headers.get("set-cookie", "")
        assert ANONYMOUS_USER_COOKIE in set_cookie

    @pytest.mark.asyncio
    async def test_degraded_user_sees_empty_sessions(
        self,
        dev_client: AsyncClient,
        auth_headers: dict[str, str],
    ):
        """测试: 已登录用户创建的会话，token 过期降级后看不到

        这是核心场景：
        1. 用户 A 以有效 token 创建会话
        2. Token 过期后降级为匿名用户
        3. 匿名用户看不到用户 A 的会话
        """
        # Step 1: 用有效 token 创建一个会话
        create_response = await dev_client.post(
            "/api/v1/sessions/",
            json={"title": "Test session from valid user"},
            headers=auth_headers,
        )
        assert create_response.status_code == 201

        # Step 2: 用有效 token 查看会话列表 - 应该能看到
        list_response = await dev_client.get("/api/v1/sessions/", headers=auth_headers)
        assert list_response.status_code == 200
        sessions = list_response.json()["items"]
        assert any(s["title"] == "Test session from valid user" for s in sessions)

        # Step 3: 用无效 token（模拟过期）查看会话列表 - 不应该看到
        degraded_response = await dev_client.get(
            "/api/v1/sessions/",
            headers={"Authorization": "Bearer expired-token-after-24h"},
        )
        assert degraded_response.status_code == 200
        assert degraded_response.headers.get("x-token-degraded") == "true"
        degraded_sessions = degraded_response.json()["items"]
        # 降级为匿名用户后，看不到注册用户的会话
        assert not any(s["title"] == "Test session from valid user" for s in degraded_sessions)

    @pytest.mark.asyncio
    async def test_degraded_sessions_isolated_per_browser(
        self,
        dev_client: AsyncClient,
    ):
        """测试: 不同的降级请求（不同 cookie）产生不同的匿名身份

        模拟两个浏览器的 token 都过期的场景：
        各自降级后，匿名 cookie 不同，会话互不可见。
        """
        # Browser 1: 无效 token，获取匿名 cookie
        response1 = await dev_client.get(
            "/api/v1/sessions/",
            headers={"Authorization": "Bearer expired-token-browser1"},
        )
        assert response1.headers.get("x-token-degraded") == "true"
        set_cookie1 = response1.headers.get("set-cookie", "")
        match1 = re.search(rf"{ANONYMOUS_USER_COOKIE}=([^;]+)", set_cookie1)
        anon_id_1 = match1.group(1) if match1 else None

        # Browser 2: 清除 cookie，模拟另一个浏览器
        dev_client.cookies.clear()
        response2 = await dev_client.get(
            "/api/v1/sessions/",
            headers={"Authorization": "Bearer expired-token-browser2"},
        )
        assert response2.headers.get("x-token-degraded") == "true"
        set_cookie2 = response2.headers.get("set-cookie", "")
        match2 = re.search(rf"{ANONYMOUS_USER_COOKIE}=([^;]+)", set_cookie2)
        anon_id_2 = match2.group(1) if match2 else None

        # Assert - 两个浏览器的匿名 ID 应该不同
        assert anon_id_1 is not None
        assert anon_id_2 is not None
        assert anon_id_1 != anon_id_2
