"""
Token 过期处理单元测试

测试 get_principal 在 JWT token 无效/过期时的行为：
1. 无效 token 返回 401（不再静默降级）
2. 有效 token 正常返回 Principal
3. 无 token 返回 401
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest


@pytest.mark.unit
class TestTokenExpiry:
    """Token 过期行为测试

    验证 get_principal 在 token 无效时统一返回 401，
    不再区分开发/生产模式进行静默降级。
    """

    def _create_mock_request(self) -> MagicMock:
        """创建 Mock Request 对象"""
        request = MagicMock()
        request.state = MagicMock(spec=[])
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value=None)
        return request

    def _create_mock_credentials(self, token: str = "invalid-token") -> MagicMock:
        """创建 Mock HTTPAuthorizationCredentials"""
        creds = MagicMock()
        creds.credentials = token
        return creds

    @pytest.mark.asyncio
    async def test_expired_token_returns_401_in_dev_mode(self):
        """测试: 开发模式下过期 token 返回 401（不再降级）"""
        from domains.identity.application.principal_service import get_principal
        from libs.exceptions import TokenError

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("expired-jwt-token")
        mock_db = AsyncMock()

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.infrastructure.authentication.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("fastapi_users_db_sqlalchemy.SQLAlchemyUserDatabase"),
            patch("domains.identity.infrastructure.user_manager.UserManager"),
        ):
            mock_settings.is_sso_auth = False
            mock_settings.is_development = True

            with pytest.raises(TokenError) as exc_info:
                await get_principal(request, credentials, mock_db)

            assert exc_info.value.code == "TOKEN_ERROR"

    @pytest.mark.asyncio
    async def test_expired_token_returns_401_in_production(self):
        """测试: 生产模式下过期 token 返回 401"""
        from domains.identity.application.principal_service import get_principal
        from libs.exceptions import TokenError

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("expired-token")
        mock_db = AsyncMock()

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.infrastructure.authentication.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("fastapi_users_db_sqlalchemy.SQLAlchemyUserDatabase"),
            patch("domains.identity.infrastructure.user_manager.UserManager"),
        ):
            mock_settings.is_sso_auth = False
            mock_settings.is_development = False

            with pytest.raises(TokenError) as exc_info:
                await get_principal(request, credentials, mock_db)

            assert exc_info.value.code == "TOKEN_ERROR"

    @pytest.mark.asyncio
    async def test_expired_token_does_not_set_degraded_flag(self):
        """测试: 过期 token 不再设置 token_degraded 标记"""
        from domains.identity.application.principal_service import get_principal
        from libs.exceptions import TokenError

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("expired-jwt")
        mock_db = AsyncMock()

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.infrastructure.authentication.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("fastapi_users_db_sqlalchemy.SQLAlchemyUserDatabase"),
            patch("domains.identity.infrastructure.user_manager.UserManager"),
        ):
            mock_settings.is_sso_auth = False
            mock_settings.is_development = True

            with pytest.raises(TokenError):
                await get_principal(request, credentials, mock_db)

        assert not hasattr(request.state, "token_degraded") or not request.state.token_degraded

    @pytest.mark.asyncio
    async def test_valid_token_returns_principal(self):
        """测试: 有效 token 正常返回 Principal"""
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("valid-jwt-token")
        mock_db = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "leo@example.com"
        mock_user.name = "Leo"
        mock_user.role = "user"
        mock_user.vendor_creator_id = None

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=mock_user)

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.infrastructure.authentication.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("fastapi_users_db_sqlalchemy.SQLAlchemyUserDatabase"),
            patch("domains.identity.infrastructure.user_manager.UserManager"),
        ):
            mock_settings.is_sso_auth = False
            principal = await get_principal(request, credentials, mock_db)

        assert principal is not None
        assert principal.email == "leo@example.com"
        assert principal.id == str(mock_user.id)

    @pytest.mark.asyncio
    async def test_no_token_returns_401_in_dev_mode(self):
        """测试: 开发模式下无 token 返回 401"""
        from domains.identity.application.principal_service import get_principal
        from libs.exceptions import AuthenticationError

        request = self._create_mock_request()
        mock_db = AsyncMock()

        with patch("domains.identity.application.principal_service.settings") as mock_settings:
            mock_settings.is_sso_auth = False
            mock_settings.is_development = True

            with pytest.raises(AuthenticationError) as exc_info:
                await get_principal(request, None, mock_db)

            assert exc_info.value.code == "AUTHENTICATION_ERROR"

    @pytest.mark.asyncio
    async def test_no_token_returns_401_in_production(self):
        """测试: 生产模式下无 token 返回 401"""
        from domains.identity.application.principal_service import get_principal
        from libs.exceptions import AuthenticationError

        request = self._create_mock_request()
        mock_db = AsyncMock()

        with patch("domains.identity.application.principal_service.settings") as mock_settings:
            mock_settings.is_sso_auth = False
            mock_settings.is_development = False

            with pytest.raises(AuthenticationError) as exc_info:
                await get_principal(request, None, mock_db)

            assert exc_info.value.code == "AUTHENTICATION_ERROR"
