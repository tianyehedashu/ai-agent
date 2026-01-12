"""
JWT Token Management - JWT 令牌管理

实现:
- Access Token 生成与验证
- Refresh Token 生成与验证
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pydantic import BaseModel

from app.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class TokenPayload(BaseModel):
    """Token 载荷"""

    sub: str  # 用户 ID
    exp: datetime  # 过期时间
    type: str  # token 类型: access / refresh
    iat: datetime | None = None  # 签发时间


def create_access_token(
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
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    now = datetime.now(timezone.utc)
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
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
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
        expires_delta = timedelta(days=settings.refresh_token_expire_days)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": now,
        "type": "refresh",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(
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
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # 检查 token 类型
        if payload.get("type") != token_type:
            logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
            return None

        return TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"]),
            type=payload["type"],
            iat=datetime.fromtimestamp(payload.get("iat", 0)) if payload.get("iat") else None,
        )

    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


def decode_token_without_verification(token: str) -> dict[str, Any] | None:
    """
    解码 Token (不验证签名)

    ⚠️ 安全警告: 此函数仅用于调试和日志记录场景。
    不要将此函数的返回值用于认证或授权判断!

    Args:
        token: JWT Token

    Returns:
        Token 载荷 (未验证, 不可信)
    """
    try:
        # nosec B105 - 此函数仅用于调试，不用于认证
        return jwt.decode(
            token,
            algorithms=["HS256"],  # 明确指定算法防止算法混淆攻击
            options={"verify_signature": False},
        )
    except Exception:
        return None
