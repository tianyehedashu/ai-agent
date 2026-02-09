"""
Token Domain Service - Token 领域服务

包含 Token 生成和验证的业务逻辑。
"""

from dataclasses import dataclass

from bootstrap.config import get_settings
from domains.identity.infrastructure.auth.jwt import create_refresh_token, verify_token
from domains.identity.infrastructure.authentication import get_jwt_strategy


@dataclass
class TokenPair:
    """Token 对，包含访问令牌和刷新令牌"""

    access_token: str
    refresh_token: str
    expires_in: int  # 过期时间（秒）


class TokenService:
    """Token 领域服务

    处理 JWT Token 的生成和验证。
    """

    async def create_token_pair(self, user) -> TokenPair:
        """为用户创建 Token 对

        Args:
            user: 用户实体

        Returns:
            TokenPair 对象
        """
        settings = get_settings()
        strategy = get_jwt_strategy()

        # 使用 FastAPI Users 的 JWT strategy 创建 access token
        # JWTStrategy 使用 jwt_expire_hours * 3600 作为 lifetime_seconds
        access_token = await strategy.write_token(user)

        # 创建 refresh token（有效期 refresh_token_expire_days）
        refresh_token = create_refresh_token(str(user.id))

        # expires_in 与 JWTStrategy 的实际 lifetime 保持一致
        expires_in = settings.jwt_expire_hours * 3600

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    def verify_refresh_token(self, refresh_token: str) -> dict | None:
        """验证刷新令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            Token payload，如果无效则返回 None
        """
        return verify_token(refresh_token, token_type="refresh")
