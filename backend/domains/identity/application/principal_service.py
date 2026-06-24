"""
Identity principal service.

统一身份解析：
- sso 模式：信任 HiGress(giikin-auth-bridge) 注入的 X-Giikin-* 身份 Header，
  校验 Internal-Key 并按 giikin user_id JIT 映射本地用户。
- local 模式：本地邮箱密码签发的 JWT（Authorization: Bearer）。
- hybrid 模式：Bearer JWT 优先；无 Bearer 或 JWT 无效时 fallback 到网关 Header。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from bootstrap.config import settings
from domains.identity.domain.types import Principal
from domains.identity.infrastructure.models.user import User
from libs.exceptions import AuthenticationError, PermissionDeniedError, TokenError
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


async def _principal_from_api_key(
    request: Request,
    credentials: "HTTPAuthorizationCredentials | None",
    db: "AsyncSession",
) -> Principal:
    """平台 API Key 认证（需 gateway:admin 或 gateway:read scope）。

    用于管理面（/api/v1/gateway/* 等）替代 JWT 的长期凭证：读操作要求
    gateway:read 或 gateway:admin；写操作额外要求 gateway:admin。
    身份解析后复用 API Key 所属 user 的 RBAC 角色与团队成员关系。
    """
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Authentication required")
    plain = credentials.credentials.strip()
    if not plain.startswith("sk_"):
        raise AuthenticationError("Authentication required")

    from domains.identity.application.api_key_use_case import ApiKeyUseCase
    from domains.identity.domain.api_key_types import ApiKeyScope
    from domains.identity.domain.services.api_key_service import ApiKeyGenerator
    from domains.identity.infrastructure.models.user import User

    encryption_key = ApiKeyGenerator.derive_encryption_key(
        settings.secret_key.get_secret_value()
    )
    use_case = ApiKeyUseCase(db, encryption_key=encryption_key)
    entity = await use_case.verify_api_key(plain)
    if entity is None or not entity.is_valid:
        raise AuthenticationError("Invalid or expired API key")

    # scope 校验：网关管理面至少需要 gateway:read
    if not entity.can_access_any({ApiKeyScope.GATEWAY_ADMIN, ApiKeyScope.GATEWAY_READ}):
        raise PermissionDeniedError(
            message="API key lacks gateway management scope (gateway:admin or gateway:read)",
            resource="ApiKeyScope",
        )
    # 写操作需要 gateway:admin
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not entity.can_access(ApiKeyScope.GATEWAY_ADMIN):
            raise PermissionDeniedError(
                message="API key lacks gateway:admin scope for write operations",
                resource="ApiKeyScope",
            )

    import uuid as _uuid

    user = await db.get(User, _uuid.UUID(entity.user_id))
    if user is None or not user.is_active:
        raise AuthenticationError("API key owner is inactive or not found")

    # 暴露 API Key 上下文供审计/中间件
    request.state.api_key_id = str(entity.id)
    request.state.api_key_scopes = sorted(s.value for s in entity.scopes)

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
    """获取当前主体（无有效身份一律 401，不支持匿名）。

    优先级：平台 API Key（sk_ 前缀，需 gateway scope）> Bearer JWT > 网关 X-Giikin-* Header。
    平台 API Key 用于管理面自动化运维（长期有效）；JWT 用于前端交互；SSO Header 用于内网。
    """
    # 平台 API Key 优先识别（sk_ 前缀，需 gateway:admin 或 gateway:read scope）
    if credentials and credentials.credentials:
        if credentials.credentials.strip().startswith("sk_"):
            return await _principal_from_api_key(request, credentials, db)

    if settings.is_sso_auth:
        return await _principal_from_gateway(request, db)
    if settings.is_hybrid_auth:
        # 有 Bearer 先试 JWT；JWT 无效（非缺失）时 fallback 到网关 Header
        if credentials and credentials.credentials:
            try:
                return await _principal_from_jwt(credentials, db)
            except (AuthenticationError, TokenError):
                pass
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
