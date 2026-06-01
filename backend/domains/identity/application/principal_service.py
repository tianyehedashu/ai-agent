"""
Identity principal service.

统一身份解析：
- sso 模式：信任 HiGress(giikin-auth-bridge) 注入的 X-Giikin-* 身份 Header，
  校验 Internal-Key 并按 giikin user_id JIT 映射本地用户。
- local 模式：本地邮箱密码签发的 JWT（Authorization: Bearer）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from bootstrap.config import settings
from domains.identity.domain.types import Principal
from domains.identity.infrastructure.models.user import User
from libs.exceptions import AuthenticationError, TokenError
from utils.logging import get_logger

if TYPE_CHECKING:
    from fastapi.security import HTTPAuthorizationCredentials
    from sqlalchemy.ext.asyncio import AsyncSession


async def _principal_from_gateway(request: Request, db: AsyncSession) -> Principal:
    """SSO 模式：解析网关注入身份并 JIT 映射本地用户。"""
    from domains.identity.application.giikin_identity_service import GiikinIdentityService
    from domains.identity.infrastructure.auth.giikin_gateway import resolve_giikin_identity

    claims = await resolve_giikin_identity(request, settings)
    if claims is None:
        raise AuthenticationError("Authentication required")

    user = await GiikinIdentityService(db).resolve_or_provision(claims)
    return Principal(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        role=user.role,
        vendor_creator_id=user.vendor_creator_id,
    )


async def _principal_from_jwt(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal:
    """local 模式：校验本地 JWT。"""
    if not credentials:
        raise AuthenticationError("Authentication required")

    from domains.identity.infrastructure.authentication import get_jwt_strategy
    from domains.identity.infrastructure.user_manager import UserManager

    strategy = get_jwt_strategy()
    user_db = SQLAlchemyUserDatabase(db, User)
    user_manager = UserManager(user_db)
    user = await strategy.read_token(credentials.credentials, user_manager)
    if user is None:
        raise TokenError("Invalid or expired token", expired=True)

    return Principal(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        role=user.role,
        vendor_creator_id=user.vendor_creator_id,
    )


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal:
    """获取当前主体（无有效身份一律 401，不支持匿名）。"""
    if settings.is_sso_auth:
        return await _principal_from_gateway(request, db)
    return await _principal_from_jwt(credentials, db)


async def get_principal_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal | None:
    """获取当前主体（可选，无身份返回 None 不抛错）。"""
    logger = get_logger(__name__)
    try:
        return await get_principal(request, credentials, db)
    except (AuthenticationError, TokenError):
        logger.debug("Optional principal resolution: no valid identity")
        return None
