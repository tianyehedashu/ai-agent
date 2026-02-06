"""
Token 降级机制单元测试

测试 get_principal 在开发模式下 JWT token 无效时的降级行为：
1. 无效 token 设置 request.state.token_degraded = True
2. 有效匿名流程不设置 token_degraded
3. 降级后返回匿名 Principal
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.identity.domain.types import ANONYMOUS_ID_PREFIX


@pytest.mark.unit
class TestTokenDegradationFlag:
    """Token 降级标记测试

    验证 get_principal 在不同场景下是否正确设置 token_degraded 标记。
    """

    def _create_mock_request(self, anonymous_cookie: str | None = None) -> MagicMock:
        """创建 Mock Request 对象"""
        request = MagicMock()
        request.state = MagicMock(spec=[])  # 空 spec，不预设属性
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)
        return request

    def _create_mock_credentials(self, token: str = "invalid-token") -> MagicMock:
        """创建 Mock HTTPAuthorizationCredentials"""
        creds = MagicMock()
        creds.credentials = token
        return creds

    @pytest.mark.asyncio
    async def test_invalid_token_sets_degraded_flag(self):
        """测试: 无效 token 在开发模式下设置 token_degraded 标记"""
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("expired-jwt-token")
        mock_db = AsyncMock()

        # Mock JWT 策略返回 None（token 无效）
        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.application.principal_service.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("domains.identity.application.principal_service.SQLAlchemyUserDatabase"),
            patch("domains.identity.application.principal_service.UserManager"),
        ):
            mock_settings.is_development = True

            # Act
            principal = await get_principal(request, credentials, mock_db, None)

        # Assert
        assert principal is not None
        assert principal.is_anonymous is True
        assert request.state.token_degraded is True
        assert hasattr(request.state, "anonymous_user_id")

    @pytest.mark.asyncio
    async def test_valid_token_no_degraded_flag(self):
        """测试: 有效 token 不设置 token_degraded 标记"""
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("valid-jwt-token")
        mock_db = AsyncMock()

        # Mock JWT 策略返回有效用户
        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "leo@example.com"
        mock_user.name = "Leo"
        mock_user.role = "user"
        mock_user.vendor_creator_id = None

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=mock_user)

        with (
            patch(
                "domains.identity.application.principal_service.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("domains.identity.application.principal_service.SQLAlchemyUserDatabase"),
            patch("domains.identity.application.principal_service.UserManager"),
        ):
            # Act
            principal = await get_principal(request, credentials, mock_db, None)

        # Assert
        assert principal is not None
        assert principal.is_anonymous is False
        assert principal.email == "leo@example.com"
        # 不应设置 token_degraded
        assert not hasattr(request.state, "token_degraded") or not request.state.token_degraded

    @pytest.mark.asyncio
    async def test_no_token_anonymous_no_degraded_flag(self):
        """测试: 无 token 的正常匿名访问不设置 token_degraded 标记"""
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        mock_db = AsyncMock()
        anonymous_id = str(uuid.uuid4())

        with patch("domains.identity.application.principal_service.settings") as mock_settings:
            mock_settings.is_development = True

            # Act - 无 credentials，有 anonymous_user_id cookie
            principal = await get_principal(request, None, mock_db, anonymous_id)

        # Assert
        assert principal is not None
        assert principal.is_anonymous is True
        # 正常匿名流程不应设置 token_degraded
        assert not hasattr(request.state, "token_degraded") or not request.state.token_degraded

    @pytest.mark.asyncio
    async def test_degraded_principal_is_anonymous(self):
        """测试: 降级后的 Principal 具有正确的匿名身份格式"""
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("bad-token")
        mock_db = AsyncMock()

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.application.principal_service.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("domains.identity.application.principal_service.SQLAlchemyUserDatabase"),
            patch("domains.identity.application.principal_service.UserManager"),
        ):
            mock_settings.is_development = True

            # Act
            principal = await get_principal(request, credentials, mock_db, None)

        # Assert - 降级后应该是格式正确的匿名 Principal
        assert principal.is_anonymous is True
        assert principal.id.startswith(ANONYMOUS_ID_PREFIX)
        assert "anonymous" in principal.email

    @pytest.mark.asyncio
    async def test_degraded_with_existing_cookie_reuses_anonymous_id(self):
        """测试: 降级时如果已有匿名 cookie，复用该 ID"""
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("expired-token")
        mock_db = AsyncMock()
        existing_anonymous_id = "existing-anon-id-12345"

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.application.principal_service.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("domains.identity.application.principal_service.SQLAlchemyUserDatabase"),
            patch("domains.identity.application.principal_service.UserManager"),
        ):
            mock_settings.is_development = True

            # Act - 带有已存在的匿名 cookie
            principal = await get_principal(request, credentials, mock_db, existing_anonymous_id)

        # Assert - 应该复用已有的 anonymous_id
        assert principal.is_anonymous is True
        assert request.state.anonymous_user_id == existing_anonymous_id
        assert request.state.token_degraded is True

    @pytest.mark.asyncio
    async def test_invalid_token_in_production_raises_401(self):
        """测试: 生产模式下无效 token 返回 401（不降级）"""
        from fastapi import HTTPException

        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("expired-token")
        mock_db = AsyncMock()

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.application.principal_service.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("domains.identity.application.principal_service.SQLAlchemyUserDatabase"),
            patch("domains.identity.application.principal_service.UserManager"),
        ):
            mock_settings.is_development = False

            # Act & Assert - 生产模式应该抛出 401
            with pytest.raises(HTTPException) as exc_info:
                await get_principal(request, credentials, mock_db, None)
            assert exc_info.value.status_code == 401
