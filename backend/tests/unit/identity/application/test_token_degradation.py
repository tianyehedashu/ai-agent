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
            mock_settings.is_hybrid_auth = False
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
            mock_settings.is_hybrid_auth = False
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
            mock_settings.is_hybrid_auth = False
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
            mock_settings.is_hybrid_auth = False
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
            mock_settings.is_hybrid_auth = False
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
            mock_settings.is_hybrid_auth = False
            mock_settings.is_development = False

            with pytest.raises(AuthenticationError) as exc_info:
                await get_principal(request, None, mock_db)

            assert exc_info.value.code == "AUTHENTICATION_ERROR"

    @pytest.mark.asyncio
    async def test_hybrid_bearer_jwt_takes_priority(self):
        """测试: hybrid 模式下 Bearer JWT 优先于网关 Header"""
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("valid-jwt-token")
        mock_db = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "local@example.com"
        mock_user.name = "LocalUser"
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
            mock_settings.is_hybrid_auth = True
            principal = await get_principal(request, credentials, mock_db)

        assert principal is not None
        assert principal.email == "local@example.com"

    @pytest.mark.asyncio
    async def test_hybrid_falls_back_to_gateway_when_jwt_invalid(self):
        """测试: hybrid 模式下 JWT 无效时 fallback 到网关 Header"""
        from domains.identity.application.giikin_identity_service import GiikinIdentityService
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        credentials = self._create_mock_credentials("expired-jwt-token")
        mock_db = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "sso@example.com"
        mock_user.name = "SSOUser"
        mock_user.role = "user"
        mock_user.vendor_creator_id = None

        mock_strategy = MagicMock()
        mock_strategy.read_token = AsyncMock(return_value=None)

        mock_claims = MagicMock()

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.infrastructure.authentication.get_jwt_strategy",
                return_value=mock_strategy,
            ),
            patch("fastapi_users_db_sqlalchemy.SQLAlchemyUserDatabase"),
            patch("domains.identity.infrastructure.user_manager.UserManager"),
            patch(
                "domains.identity.infrastructure.auth.giikin_gateway.resolve_giikin_identity",
                return_value=mock_claims,
            ),
            patch.object(GiikinIdentityService, "resolve_or_provision", return_value=mock_user),
        ):
            mock_settings.is_sso_auth = False
            mock_settings.is_hybrid_auth = True
            principal = await get_principal(request, credentials, mock_db)

        assert principal is not None
        assert principal.email == "sso@example.com"

    @pytest.mark.asyncio
    async def test_hybrid_sk_key_scope_denied_falls_back_to_gateway(self):
        """hybrid 模式下 sk_ Key scope 不足时 fallback 到网关 Header（不直接 403）。"""
        from domains.identity.application import principal_service
        from domains.identity.application.principal_service import get_principal
        from libs.exceptions import PermissionDeniedError

        request = self._create_mock_request()
        request.method = "GET"
        credentials = self._create_mock_credentials("sk_live_xxx")
        mock_db = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "sso-fallback@example.com"
        mock_user.name = "SSOUser"
        mock_user.role = "user"
        mock_user.vendor_creator_id = None
        principal = principal_service.Principal(
            id=str(mock_user.id),
            email=mock_user.email,
            name=mock_user.name,
            role=mock_user.role,
            vendor_creator_id=None,
        )

        with (
            patch.object(principal_service, "settings") as mock_settings,
            patch.object(
                principal_service,
                "_principal_from_api_key",
                AsyncMock(side_effect=PermissionDeniedError(message="x", resource="ApiKeyScope")),
            ),
            patch.object(
                principal_service,
                "_principal_from_gateway",
                AsyncMock(return_value=principal),
            ),
        ):
            mock_settings.is_sso_auth = False
            mock_settings.is_hybrid_auth = True
            result = await get_principal(request, credentials, mock_db)

        assert result.email == "sso-fallback@example.com"

    @pytest.mark.asyncio
    async def test_optional_principal_returns_none_on_scope_denied(self):
        """可选认证下 sk_ Key scope 不足应降级为匿名（None），而非 403。"""
        from domains.identity.application import principal_service
        from domains.identity.application.principal_service import get_principal_optional
        from libs.exceptions import PermissionDeniedError

        request = self._create_mock_request()
        mock_db = AsyncMock()

        with patch.object(
            principal_service,
            "get_principal",
            AsyncMock(side_effect=PermissionDeniedError(message="x", resource="ApiKeyScope")),
        ):
            result = await get_principal_optional(request, None, mock_db)

        assert result is None

    @pytest.mark.parametrize(
        ("method", "path", "expected"),
        [
            ("GET", "/api/v1/gateway/pricing/upstream", True),
            ("HEAD", "/api/v1/gateway/pricing/upstream", True),
            ("OPTIONS", "/api/v1/gateway/pricing/upstream", True),
            # 显式只读 POST 白名单
            ("POST", "/api/v1/gateway/pricing/estimate", True),
            ("POST", "/api/v1/gateway/pricing/estimate/", True),
            # 其它 POST 仍按写处理
            ("POST", "/api/v1/gateway/pricing/upstream", False),
            ("PUT", "/api/v1/gateway/pricing/estimate", False),
            ("DELETE", "/api/v1/gateway/credentials/x", False),
        ],
    )
    def test_is_read_only_api_request(self, method: str, path: str, expected: bool):
        from domains.identity.application.principal_service import _is_read_only_api_request

        request = MagicMock()
        request.method = method
        request.url = MagicMock()
        request.url.path = path
        assert _is_read_only_api_request(request) is expected

    @pytest.mark.asyncio
    async def test_hybrid_no_bearer_uses_gateway(self):
        """测试: hybrid 模式下无 Bearer 时直接走网关 Header"""
        from domains.identity.application.giikin_identity_service import GiikinIdentityService
        from domains.identity.application.principal_service import get_principal

        request = self._create_mock_request()
        mock_db = AsyncMock()

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.email = "sso-no-bearer@example.com"
        mock_user.name = "SSOUser"
        mock_user.role = "user"
        mock_user.vendor_creator_id = None

        mock_claims = MagicMock()

        with (
            patch("domains.identity.application.principal_service.settings") as mock_settings,
            patch(
                "domains.identity.infrastructure.auth.giikin_gateway.resolve_giikin_identity",
                return_value=mock_claims,
            ),
            patch.object(GiikinIdentityService, "resolve_or_provision", return_value=mock_user),
        ):
            mock_settings.is_sso_auth = False
            mock_settings.is_hybrid_auth = True
            principal = await get_principal(request, None, mock_db)

        assert principal is not None
        assert principal.email == "sso-no-bearer@example.com"
