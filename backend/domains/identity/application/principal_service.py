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

# 显式的「只读 POST」端点（按 path 后缀匹配，与挂载前缀无关）：这些 POST 语义上是
# 读/计算（非状态变更），允许 ``gateway:read`` 平台 Key 访问；其余非 GET 请求仍按写处理
# 要求 ``gateway:admin``。新增条目须确保该端点确实无副作用。
_READ_ONLY_POST_PATH_SUFFIXES: frozenset[str] = frozenset(
    {
        "/pricing/estimate",  # 用量成本预估，纯计算无副作用
    }
)


def _is_read_only_api_request(request: Request) -> bool:
    """API Key scope 判定用：是否为只读请求（读方法或显式只读 POST 白名单）。"""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True
    if request.method == "POST":
        path = request.url.path.rstrip("/")
        return any(path.endswith(suffix) for suffix in _READ_ONLY_POST_PATH_SUFFIXES)
    return False


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
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal:
    """平台 API Key 认证（需 gateway:admin 或 gateway:read scope）。

    用于管理面（/api/v1/gateway/* 等）替代 JWT 的长期凭证：读操作要求
    gateway:read 或 gateway:admin；写操作额外要求 gateway:admin。
    身份解析后复用 API Key 所属 user 的 RBAC 角色与团队成员关系。
    """
    logger = get_logger(__name__)
    if not credentials or not credentials.credentials:
        raise AuthenticationError("Authentication required")
    plain = credentials.credentials.strip()
    if not plain.startswith("sk_"):
        raise AuthenticationError("Authentication required")

    from domains.identity.application.api_key_use_case import ApiKeyUseCase
    from domains.identity.domain.api_key_types import ApiKeyScope
    from domains.identity.domain.services.api_key_service import ApiKeyGenerator
    from domains.identity.infrastructure.models.user import User

    try:
        encryption_key = ApiKeyGenerator.derive_encryption_key(
            settings.secret_key.get_secret_value()
        )
        use_case = ApiKeyUseCase(db, encryption_key=encryption_key)
        entity = await use_case.verify_api_key(plain)
    except AuthenticationError:
        raise
    except Exception:
        logger.exception("API key verification failed unexpectedly")
        raise AuthenticationError("API key verification failed")

    if entity is None or not entity.is_valid:
        raise AuthenticationError("Invalid or expired API key")

    # scope 校验：网关管理面至少需要 gateway:read
    if not entity.can_access_any({ApiKeyScope.GATEWAY_ADMIN, ApiKeyScope.GATEWAY_READ}):
        logger.warning(
            "API key %s rejected: missing gateway scopes (has=%s)",
            entity.id,
            sorted(s.value for s in entity.scopes),
        )
        raise PermissionDeniedError(
            message="API key lacks gateway management scope (gateway:admin or gateway:read)",
            resource="ApiKeyScope",
        )
    # 写操作需要 gateway:admin；只读请求（含显式只读 POST 白名单）gateway:read 即可
    if not _is_read_only_api_request(request) and not entity.can_access(
        ApiKeyScope.GATEWAY_ADMIN
    ):
        logger.warning(
            "API key %s rejected: write operation requires gateway:admin (has=%s, method=%s, path=%s)",
            entity.id,
            sorted(s.value for s in entity.scopes),
            request.method,
            request.url.path,
        )
        raise PermissionDeniedError(
            message="API key lacks gateway:admin scope for write operations",
            resource="ApiKeyScope",
        )

    user = await db.get(User, entity.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("API key owner is inactive or not found")

    # 暴露 API Key 上下文供审计/中间件
    request.state.api_key_id = str(entity.id)
    request.state.api_key_scopes = sorted(s.value for s in entity.scopes)

    logger.debug(
        "API key %s authenticated user %s (scopes=%s)",
        entity.id,
        user.id,
        request.state.api_key_scopes,
    )

    return Principal(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        role=user.role,
        vendor_creator_id=user.vendor_creator_id,
    )


def _has_sk_key(credentials: HTTPAuthorizationCredentials | None) -> bool:
    return bool(
        credentials
        and credentials.credentials
        and credentials.credentials.strip().startswith("sk_")
    )


async def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal:
    """获取当前主体（无有效身份一律 401，不支持匿名）。

    优先级：平台 API Key（sk_ 前缀，需 gateway scope）> Bearer JWT > 网关 X-Giikin-* Header。
    平台 API Key 用于管理面自动化运维（长期有效）；JWT 用于前端交互；SSO Header 用于内网。

    在 sso/hybrid 模式下，sk_ Key 解析失败（无效或 scope 不足）会像 JWT 失败一样
    fallback 到网关 Header（而非直接 403），避免仅持 ``gateway:proxy`` 等非管理 scope
    的合法平台 Key 阻断 SSO 身份回退。local 模式无回退目标，sk_ 失败即终态抛出。
    """
    has_sk = _has_sk_key(credentials)

    if settings.is_sso_auth:
        if has_sk:
            try:
                return await _principal_from_api_key(request, credentials, db)
            except (AuthenticationError, TokenError, PermissionDeniedError):
                pass
        return await _principal_from_gateway(request, db)

    if settings.is_hybrid_auth:
        if has_sk:
            # sk_ 优先；失败回退网关 Header（与下方 JWT 回退一致）
            try:
                return await _principal_from_api_key(request, credentials, db)
            except (AuthenticationError, TokenError, PermissionDeniedError):
                pass
        elif credentials and credentials.credentials:
            # 有 Bearer JWT 先试；JWT 无效（非缺失）时 fallback 到网关 Header
            try:
                return await _principal_from_jwt(credentials, db)
            except (AuthenticationError, TokenError):
                pass
        return await _principal_from_gateway(request, db)

    # local 模式：sk_ Key 或本地 JWT，无网关 Header 回退
    if has_sk:
        return await _principal_from_api_key(request, credentials, db)
    return await _principal_from_jwt(credentials, db)


async def get_principal_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
) -> Principal | None:
    """获取当前主体（可选，无身份返回 None 不抛错）。

    除认证失败外，平台 API Key 的 scope 不足（``PermissionDeniedError``）也视为"无可用身份"
    降级为匿名，避免仅持非管理 scope 的 Key 在可选认证端点上误报 403。
    """
    logger = get_logger(__name__)
    try:
        return await get_principal(request, credentials, db)
    except (AuthenticationError, TokenError, PermissionDeniedError):
        logger.debug("Optional principal resolution: no valid identity")
        return None
