"""
Identity principal service.

Provides unified principal resolution, including anonymous users in development.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from fastapi import HTTPException, Request, status
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from bootstrap.config import settings
from domains.identity.domain.types import Principal
from domains.identity.infrastructure.authentication import get_jwt_strategy
from domains.identity.infrastructure.models.user import User
from domains.identity.infrastructure.user_manager import UserManager
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


async def _get_or_create_anonymous_principal(
    db: AsyncSession,
    anonymous_id: str,
) -> Principal | None:
    """获取或创建匿名主体（开发环境专用）

    注意：匿名用户不再创建 User 记录，只返回 Principal 对象。
    匿名用户的会话和消息通过 anonymous_user_id 字段关联。
    """
    # 直接返回 Principal，不创建 User 记录
    # 匿名用户的会话通过 Session.anonymous_user_id 字段关联
    return Principal(
        id=Principal.make_anonymous_id(anonymous_id),
        email=Principal.make_anonymous_email(anonymous_id),
        name=f"Anonymous User ({anonymous_id[:8]})",
        is_anonymous=True,
        role="user",  # 匿名用户默认为普通用户
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
            principal = await _get_or_create_anonymous_principal(db, anonymous_user_id)
            if principal:
                return principal

            logger.error("Failed to create or retrieve anonymous user")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create anonymous user. Please check database connection.",
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    strategy = get_jwt_strategy()
    user_db = SQLAlchemyUserDatabase(db, User)
    user_manager = UserManager(user_db)
    user = await strategy.read_token(token, user_manager)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Principal(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        is_anonymous=False,
        role=user.role,  # 从 User 模型获取角色
    )


async def get_principal_optional(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal | None:
    """获取当前主体（可选）"""
    if not credentials:
        return None

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
    )
