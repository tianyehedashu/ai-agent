"""
JWT Token Management - JWT 令牌管理

实现:
- Access Token 生成与验证
- Refresh Token 生成与验证
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import jwt
from pydantic import BaseModel

from utils.logging import get_logger

if TYPE_CHECKING:
    from core.config import AuthConfig

logger = get_logger(__name__)

# 全局 JWT Manager 实例（通过 init_jwt_manager 初始化）
_jwt_manager: "JWTManager | None" = None


class TokenPayload(BaseModel):
    """Token 载荷"""

    sub: str  # 用户 ID
    exp: datetime  # 过期时间
    type: str  # token 类型: access / refresh
    iat: datetime | None = None  # 签发时间


class JWTManager:
    """JWT 管理器"""

    def __init__(self, config: "AuthConfig") -> None:
        """
        初始化 JWT 管理器

        Args:
            config: 认证配置（通过依赖注入传入，避免依赖应用层）
        """
        self.config = config

    def create_access_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """
        创建访问令牌

        Args:
            user_id: 用户 ID
            expires_delta: 过期时间增量
            extra_claims: 额外声明

        Returns:
            JWT Token
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.config.access_token_expire_minutes)

        now = datetime.now(UTC)
        expire = now + expires_delta

        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "type": "access",
        }

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(
            payload,
            self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm,
        )

    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: timedelta | None = None,
    ) -> str:
        """
        创建刷新令牌

        Args:
            user_id: 用户 ID
            expires_delta: 过期时间增量

        Returns:
            JWT Token
        """
        if expires_delta is None:
            expires_delta = timedelta(days=self.config.refresh_token_expire_days)

        now = datetime.now(UTC)
        expire = now + expires_delta

        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": now,
            "type": "refresh",
        }

        return jwt.encode(
            payload,
            self.config.jwt_secret_key,
            algorithm=self.config.jwt_algorithm,
        )

    def verify_token(
        self,
        token: str,
        token_type: str = "access",
    ) -> TokenPayload | None:
        """
        验证令牌

        Args:
            token: JWT Token
            token_type: 期望的 token 类型

        Returns:
            Token 载荷，验证失败返回 None
        """
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm],
            )

            # 检查 token 类型
            if payload.get("type") != token_type:
                logger.warning(
                    "Invalid token type: expected %s, got %s",
                    token_type,
                    payload.get("type"),
                )
                return None

            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
                type=payload["type"],
                iat=datetime.fromtimestamp(payload.get("iat", 0), tz=UTC)
                if payload.get("iat")
                else None,
            )

        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token: %s", e)
            return None


def init_jwt_manager(config: "AuthConfig") -> None:
    """
    初始化全局 JWT Manager

    在应用启动时调用，用于设置全局实例

    Args:
        config: 认证配置
    """
    global _jwt_manager
    _jwt_manager = JWTManager(config)


def get_jwt_manager() -> JWTManager:
    """
    获取全局 JWT Manager 实例

    Returns:
        JWTManager 实例

    Raises:
        RuntimeError: 如果 JWT Manager 未初始化
    """
    if _jwt_manager is None:
        raise RuntimeError("JWT Manager not initialized. Call init_jwt_manager() first.")
    return _jwt_manager


# 便捷函数接口（向后兼容）
def create_access_token(
    user_id: str,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    创建访问令牌（便捷函数）

    Args:
        user_id: 用户 ID
        expires_delta: 过期时间增量
        extra_claims: 额外声明

    Returns:
        JWT Token
    """
    return get_jwt_manager().create_access_token(
        user_id=user_id,
        expires_delta=expires_delta,
        extra_claims=extra_claims,
    )


def create_refresh_token(
    user_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    创建刷新令牌（便捷函数）

    Args:
        user_id: 用户 ID
        expires_delta: 过期时间增量

    Returns:
        JWT Token
    """
    return get_jwt_manager().create_refresh_token(
        user_id=user_id,
        expires_delta=expires_delta,
    )


def verify_token(
    token: str,
    token_type: str = "access",
) -> TokenPayload | None:
    """
    验证令牌（便捷函数）

    Args:
        token: JWT Token
        token_type: 期望的 token 类型

    Returns:
        Token 载荷，验证失败返回 None
    """
    return get_jwt_manager().verify_token(token=token, token_type=token_type)
