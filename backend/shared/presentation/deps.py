"""
API Dependencies - API 依赖注入

提供 FastAPI 路由的依赖注入，遵循依赖倒置原则
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated, Protocol

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from shared.infrastructure.db.database import get_session
from domains.agent_catalog.application import AgentUseCase
from domains.identity.application import (
    ANONYMOUS_USER_COOKIE,
    UserUseCase,
    get_principal,
    get_principal_optional,
)

# 重导出 ANONYMOUS_USER_COOKIE，方便外部使用
__all__ = [
    "ANONYMOUS_USER_COOKIE",
    "AuthUser",
    "DbSession",
    "OptionalUser",
    "RequiredAuthUser",
    "SessionLike",
    "check_ownership",
    "check_ownership_or_public",
    "check_session_ownership",
    "get_agent_service",
    "get_chat_service",
    "get_checkpoint_service",
    "get_current_user",
    "get_current_user_optional",
    "get_db",
    "get_memory_service",
    "get_session_service",
    "get_stats_service",
    "get_title_service",
    "get_user_service",
    "require_auth",
]
from domains.runtime.application import ChatUseCase, SessionUseCase, TitleUseCase
from domains.runtime.application.checkpoint_service import CheckpointService
from domains.runtime.application.memory_service import MemoryService
from domains.runtime.application.stats_service import StatsService
from exceptions import PermissionDeniedError
from shared.kernel.types import Principal
from shared.presentation.schemas import CurrentUser

if TYPE_CHECKING:
    import uuid

security = HTTPBearer(auto_error=False)


# =============================================================================
# 类型协议
# =============================================================================


class SessionLike(Protocol):
    """会话协议（用于 check_session_ownership 的 duck typing）"""

    user_id: "uuid.UUID | None"
    anonymous_user_id: str | None


# =============================================================================
# 数据库会话依赖
# =============================================================================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


# =============================================================================
# 认证依赖
# =============================================================================


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
    anonymous_user_id: str | None = Cookie(default=None, alias=ANONYMOUS_USER_COOKIE),
) -> CurrentUser:
    """获取当前用户"""
    principal = await get_principal(request, credentials, db, anonymous_user_id)
    return CurrentUser(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        is_anonymous=principal.is_anonymous,
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    """获取当前用户（可选）"""
    principal = await get_principal_optional(credentials, db)
    if not principal:
        return None
    return CurrentUser(
        id=principal.id,
        email=principal.email,
        name=principal.name,
        is_anonymous=principal.is_anonymous,
    )


async def require_auth(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求必须认证（非匿名）"""
    if settings.is_development:
        return current_user
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


# 类型别名
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
RequiredAuthUser = Annotated[CurrentUser, Depends(require_auth)]
OptionalUser = Annotated[CurrentUser | None, Depends(get_current_user_optional)]


# =============================================================================
# 权限检查辅助函数
# =============================================================================


def check_ownership(
    resource_user_id: str,
    current_user_id: str,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权"""
    if str(resource_user_id) != str(current_user_id):
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def check_ownership_or_public(
    resource_user_id: str,
    current_user_id: str,
    is_public: bool,
    resource_name: str = "Resource",
) -> None:
    """检查资源所有权或是否公开"""
    if str(resource_user_id) != str(current_user_id) and not is_public:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def check_session_ownership(
    session: "SessionLike",
    current_user: CurrentUser,
) -> None:
    """检查会话所有权（支持注册用户和匿名用户）"""
    if current_user.is_anonymous:
        user_anonymous_id = Principal.extract_anonymous_id(current_user.id)
        if session.anonymous_user_id != user_anonymous_id:
            raise PermissionDeniedError(
                message="You don't have permission to access this session",
                resource="Session",
            )
    else:
        if str(session.user_id) != current_user.id:
            raise PermissionDeniedError(
                message="You don't have permission to access this session",
                resource="Session",
            )


# =============================================================================
# 服务依赖
# =============================================================================


async def get_user_service(db: DbSession) -> UserUseCase:
    """获取用户服务"""
    return UserUseCase(db)


async def get_agent_service(db: DbSession) -> AgentUseCase:
    """获取 Agent 服务"""
    return AgentUseCase(db)


async def get_session_service(db: DbSession) -> SessionUseCase:
    """获取会话服务"""
    return SessionUseCase(db)


async def get_title_service(db: DbSession) -> TitleUseCase:
    """获取标题服务"""
    return TitleUseCase(db=db)


async def get_chat_service(
    db: DbSession,
    request: Request,
) -> ChatUseCase:
    """获取对话服务"""
    checkpointer = getattr(request.app.state, "checkpointer", None)
    return ChatUseCase(db, checkpointer=checkpointer)


async def get_checkpoint_service(db: DbSession) -> CheckpointService:
    """获取检查点服务"""
    return CheckpointService(db)


async def get_memory_service(db: DbSession) -> MemoryService:
    """获取记忆服务"""
    return MemoryService(db)


async def get_stats_service(db: DbSession) -> StatsService:
    """获取统计服务"""
    return StatsService(db)
