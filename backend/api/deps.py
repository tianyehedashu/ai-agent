"""
API Dependencies - API 依赖注入

提供 FastAPI 路由的依赖注入，遵循依赖倒置原则。
"""

from collections.abc import AsyncGenerator
import sys
import traceback
from typing import Annotated
import uuid

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from db.database import get_session
from exceptions import PermissionDeniedError
from schemas.user import CurrentUser
from services.agent import AgentService
from services.chat import ChatService
from services.checkpoint import CheckpointService
from services.memory import MemoryService
from services.session import SessionService
from services.stats import StatsService
from services.title import TitleService
from services.user import UserService
from utils.logging import get_logger

security = HTTPBearer(auto_error=False)

# 匿名用户 Cookie 名称
ANONYMOUS_USER_COOKIE = "anonymous_user_id"


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


async def _get_or_create_anonymous_user(
    db: AsyncSession,
    anonymous_id: str,
) -> CurrentUser | None:
    """获取或创建匿名用户

    为每个独立的 anonymous_id 创建独立的匿名用户，实现多匿名用户隔离。

    Args:
        db: 数据库会话
        anonymous_id: 匿名用户标识（来自 Cookie 或新生成）

    Returns:
        CurrentUser 或 None（如果创建失败）
    """
    logger = get_logger(__name__)
    # 使用 anonymous_id 生成唯一邮箱，实现用户隔离
    anonymous_email = f"anonymous-{anonymous_id}@local"
    user_service = UserService(db)

    try:
        # 先尝试通过邮箱查找匿名用户
        user = await user_service.get_by_email(anonymous_email)

        if not user:
            # 如果不存在，创建新的匿名用户
            try:
                user = await user_service.create(
                    email=anonymous_email,
                    password=f"anonymous-{anonymous_id}",  # 随机密码，不会用于登录
                    name=f"Anonymous User ({anonymous_id[:8]})",
                )
                logger.info("Created new anonymous user: %s", anonymous_email)
            except Exception as e:
                # 如果创建失败（可能因为并发创建），再次尝试获取
                logger.warning("Failed to create anonymous user, will retry: %s", e)
                # 开发环境下也直接输出
                if settings.is_development:
                    print("=" * 80, file=sys.stderr)
                    print(
                        f"ERROR creating anonymous user: {type(e).__name__}: {e}",
                        file=sys.stderr,
                    )
                    traceback.print_exc(file=sys.stderr)
                    print("=" * 80, file=sys.stderr)
                # 再次尝试获取用户（可能其他请求已经创建了）
                user = await user_service.get_by_email(anonymous_email)

        if user:
            return CurrentUser(
                id=str(user.id),
                email=user.email,
                name=user.name or f"Anonymous User ({anonymous_id[:8]})",
                is_anonymous=True,
            )
    except Exception as e:
        # 捕获所有异常并记录
        logger.exception("Error in _get_or_create_anonymous_user: %s", e)
        if settings.is_development:
            print("=" * 80, file=sys.stderr)
            print(
                f"ERROR in _get_or_create_anonymous_user: {type(e).__name__}: {e}", file=sys.stderr
            )
            traceback.print_exc(file=sys.stderr)
            print("=" * 80, file=sys.stderr)
        raise

    return None


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
    anonymous_user_id: str | None = Cookie(default=None, alias=ANONYMOUS_USER_COOKIE),
) -> CurrentUser:
    """
    获取当前用户

    在开发模式下返回匿名用户（基于 Cookie 隔离），生产模式下需要有效 Token。

    匿名用户隔离机制：
    - 每个浏览器/客户端通过 Cookie 获得独立的 anonymous_user_id
    - 不同的 anonymous_user_id 对应不同的用户记录
    - 实现多匿名用户同时访问时的完全隔离
    """
    logger = get_logger(__name__)

    if not credentials:
        if settings.is_development:
            # 开发模式：基于 Cookie 的匿名用户隔离
            # 如果没有 Cookie，生成新的 anonymous_id
            if not anonymous_user_id:
                anonymous_user_id = str(uuid.uuid4())
                logger.info("Generated new anonymous_user_id: %s", anonymous_user_id[:8])

            # 将 anonymous_id 存储到 request.state，供响应中间件设置 Cookie
            request.state.anonymous_user_id = anonymous_user_id

            # 获取或创建匿名用户
            current_user = await _get_or_create_anonymous_user(db, anonymous_user_id)

            if current_user:
                return current_user
            else:
                logger.error("Failed to create or retrieve anonymous user")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create anonymous user. Please check database connection.",
                )
        else:
            # 生产模式下不允许匿名用户
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

    token = credentials.credentials
    user_service = UserService(db)

    user = await user_service.get_user_from_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        is_anonymous=False,
    )


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser | None:
    """
    获取当前用户（可选）

    如果没有认证则返回 None。
    """
    if not credentials:
        return None

    token = credentials.credentials
    user_service = UserService(db)

    user = await user_service.get_user_from_token(token)
    if not user:
        return None

    return CurrentUser(
        id=str(user.id),
        email=user.email,
        name=user.name or "",
        is_anonymous=False,
    )


async def require_auth(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """要求必须认证（非匿名）

    在开发模式下允许匿名用户，生产模式下要求真实认证。
    """
    # 开发模式下允许匿名用户
    if settings.is_development:
        return current_user

    # 生产模式下要求真实认证
    if current_user.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return current_user


# 类型别名，方便使用
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
    """
    检查资源所有权

    Args:
        resource_user_id: 资源所属用户 ID
        current_user_id: 当前用户 ID
        resource_name: 资源名称（用于错误消息）

    Raises:
        PermissionDeniedError: 当用户无权访问资源时
    """
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
    """
    检查资源所有权或是否公开

    Args:
        resource_user_id: 资源所属用户 ID
        current_user_id: 当前用户 ID
        is_public: 资源是否公开
        resource_name: 资源名称

    Raises:
        PermissionDeniedError: 当用户无权访问资源且资源非公开时
    """
    if str(resource_user_id) != str(current_user_id) and not is_public:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


# =============================================================================
# 服务依赖 - 接收数据库会话
# =============================================================================


async def get_user_service(db: DbSession) -> UserService:
    """获取用户服务"""
    return UserService(db)


async def get_agent_service(db: DbSession) -> AgentService:
    """获取 Agent 服务"""
    return AgentService(db)


async def get_session_service(db: DbSession) -> SessionService:
    """获取会话服务"""
    return SessionService(db)


async def get_title_service(db: DbSession) -> TitleService:
    """获取标题服务"""
    return TitleService(db=db)


async def get_chat_service(
    db: DbSession,
    request: Request,
) -> ChatService:
    """获取对话服务"""
    # 从应用状态获取全局 checkpointer（在应用启动时初始化）
    checkpointer = getattr(request.app.state, "checkpointer", None)
    return ChatService(db, checkpointer=checkpointer)


async def get_checkpoint_service(db: DbSession) -> CheckpointService:
    """获取检查点服务"""
    return CheckpointService(db)


async def get_memory_service(db: DbSession) -> MemoryService:
    """获取记忆服务"""
    return MemoryService(db)


async def get_stats_service(db: DbSession) -> StatsService:
    """获取统计服务"""
    return StatsService(db)
