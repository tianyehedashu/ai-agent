"""JWT Token 应用服务（生成与校验，依赖 infrastructure 适配）。"""

from __future__ import annotations

from dataclasses import dataclass

from bootstrap.config import get_settings
from domains.identity.infrastructure.auth.jwt import (
    TokenPayload,
    create_refresh_token,
    verify_token,
)
from domains.identity.infrastructure.authentication import get_jwt_strategy


@dataclass
class TokenPair:
    """Token 对，包含访问令牌和刷新令牌"""

    access_token: str
    refresh_token: str
    expires_in: int


class TokenService:
    """处理 JWT Token 的生成和验证。"""

    async def create_token_pair(self, user: object) -> TokenPair:
        settings = get_settings()
        strategy = get_jwt_strategy()
        access_token = await strategy.write_token(user)
        refresh_token = create_refresh_token(str(user.id))
        expires_in = settings.jwt_expire_hours * 3600
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )

    def verify_refresh_token(self, refresh_token: str) -> TokenPayload | None:
        return verify_token(refresh_token, token_type="refresh")


__all__ = ["TokenPair", "TokenPayload", "TokenService"]
