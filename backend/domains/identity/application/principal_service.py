"""
Identity principal service.

Provides unified principal resolution, including anonymous users in development.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from fastapi import Request
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from bootstrap.config import settings
from domains.identity.domain.anonymous_tenant import normalize_anonymous_cookie_id
from domains.identity.domain.types import Principal
from domains.identity.infrastructure.models.user import User
from libs.exceptions import AuthenticationError, TokenError
from utils.logging import get_logger

if TYPE_CHECKING:
    from fastapi.security import HTTPAuthorizationCredentials
    from sqlalchemy.ext.asyncio import AsyncSession

# =============================================================================
# 匿名用户常量（集中定义，供其他模块导入）
# =============================================================================
ANONYMOUS_USER_COOKIE = "anonymous_user_id"
ANONYMOUS_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year
ANONYMOUS_USER_HEADER = "X-Anonymous-User-Id"


def build_anonymous_principal(anonymous_id: str) -> Principal:
    """由 cookie ID 构建内存 Principal（不写 DB）。"""
    cookie_id = normalize_anonymous_cookie_id(anonymous_id)
    return Principal(
        id=Principal.make_anonymous_id(cookie_id),
        email=Principal.make_anonymous_email(cookie_id),
        name=f"Anonymous ({cookie_id[:8]})",
        is_anonymous=True,
        role="anonymous",
    )


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
    anonymous_user_id: str | None,
) -> Principal:
    """
    获取当前主体（开发环境支持匿名）

    认证策略（按优先级）：
    1. JWT Token (Authorization: Bearer) - 已认证用户
    2. Cookie (anonymous_user_id) - 匿名用户（浏览器自动发送）
    3. Header (X-Anonymous-User-Id) - 匿名用户备用方案（Cookie 丢失时）
    4. 生成新的 anonymous_user_id - 首次访问
    """
    logger = get_logger(__name__)

    if not credentials:
        # INFO 级别日志：帮助诊断 401 错误（DEBUG 级别可能不会显示）
        logger.info(
            "Auth check - app_env=%s, is_development=%s, anonymous_user_id=%s, header=%s",
            settings.app_env,
            settings.is_development,
            anonymous_user_id,
            request.headers.get("X-Anonymous-User-Id"),
        )
        if settings.is_development:
            # 优先使用 Cookie 中的 anonymous_user_id
            # 如果 Cookie 丢失，尝试从请求头获取（前端 localStorage 备用方案）
            if not anonymous_user_id:
                anonymous_user_id = request.headers.get("X-Anonymous-User-Id")
                if anonymous_user_id:
                    logger.debug("Using anonymous_user_id from header: %s", anonymous_user_id[:8])

            # 如果都没有，生成新的
            if not anonymous_user_id:
                anonymous_user_id = str(uuid.uuid4())
                logger.info("Generated new anonymous_user_id: %s", anonymous_user_id[:8])

            request.state.anonymous_user_id = anonymous_user_id
            return build_anonymous_principal(anonymous_user_id)

        # 记录为什么返回 401（非开发环境需要认证）
        logger.warning(
            "Authentication required but not in development mode. app_env=%s, is_development=%s",
            settings.app_env,
            settings.is_development,
        )
        raise AuthenticationError("Authentication required")

    from domains.identity.infrastructure.authentication import get_jwt_strategy
    from domains.identity.infrastructure.user_manager import UserManager

    token = credentials.credentials
    strategy = get_jwt_strategy()
    user_db = SQLAlchemyUserDatabase(db, User)
    user_manager = UserManager(user_db)
    user = await strategy.read_token(token, user_manager)
    if user is None:
        logger.warning("Invalid or expired JWT token, returning 401")
        raise TokenError("Invalid or expired token", expired=True)

    return Principal(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        is_anonymous=False,
        role=user.role,  # 从 User 模型获取角色
        vendor_creator_id=user.vendor_creator_id,
    )


async def get_principal_optional(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal | None:
    """获取当前主体（可选）"""
    if not credentials:
        return None

    from domains.identity.infrastructure.authentication import get_jwt_strategy
    from domains.identity.infrastructure.user_manager import UserManager

    token = credentials.credentials
    strategy = get_jwt_strategy()
    user_db = SQLAlchemyUserDatabase(db, User)
    user_manager = UserManager(user_db)
    user = await strategy.read_token(token, user_manager)
    if user is None:
        return None

    return Principal(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        is_anonymous=False,
        role=user.role,  # 从 User 模型获取角色
        vendor_creator_id=user.vendor_creator_id,
    )
