"""
Token Domain Service - Token 领域服务

包含 Token 生成和验证的业务逻辑。
"""

from dataclasses import dataclass

from bootstrap.config import get_settings
from domains.identity.infrastructure.authentication import get_jwt_strategy
from shared.infrastructure.auth.jwt import create_refresh_token, verify_token


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
        access_token = await strategy.write_token(user)

        # 创建 refresh token
        refresh_token = create_refresh_token(str(user.id))

        expires_in = settings.access_token_expire_minutes * 60

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
