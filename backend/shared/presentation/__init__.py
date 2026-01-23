"""Shared presentation layer components.

跨领域共享的表示层组件：
- deps: FastAPI 依赖注入
- schemas: 跨领域共享的 Pydantic 模型
- errors: 错误消息常量
- message_schemas: 消息相关模式
"""

from shared.presentation.deps import (
    ANONYMOUS_USER_COOKIE,
    AuthUser,
    DbSession,
    OptionalUser,
    RequiredAuthUser,
    check_ownership,
    check_ownership_or_public,
    check_session_ownership,
    get_agent_service,
    get_chat_service,
    get_checkpoint_service,
    get_current_user,
    get_current_user_optional,
    get_db,
    get_memory_service,
    get_session_service,
    get_stats_service,
    get_title_service,
    get_user_service,
    require_auth,
)
from shared.presentation.errors import (
    ACCESS_DENIED,
    AGENT_NOT_FOUND,
    BAD_REQUEST,
    INSUFFICIENT_PERMISSIONS,
    INTERNAL_ERROR,
    INVALID_CREDENTIALS,
    INVALID_TOKEN,
    SESSION_NOT_FOUND,
    TOKEN_EXPIRED,
    UNAUTHORIZED,
    USER_NOT_FOUND,
    VERSION_NOT_FOUND,
    WORKFLOW_NOT_FOUND,
)
from shared.presentation.schemas import CurrentUser

__all__ = [
    # Auth
    "ANONYMOUS_USER_COOKIE",
    "AuthUser",
    "CurrentUser",
    "DbSession",
    "OptionalUser",
    "RequiredAuthUser",
    # Ownership checks
    "check_ownership",
    "check_ownership_or_public",
    "check_session_ownership",
    # Services
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
    # Errors
    "ACCESS_DENIED",
    "AGENT_NOT_FOUND",
    "BAD_REQUEST",
    "INSUFFICIENT_PERMISSIONS",
    "INTERNAL_ERROR",
    "INVALID_CREDENTIALS",
    "INVALID_TOKEN",
    "SESSION_NOT_FOUND",
    "TOKEN_EXPIRED",
    "UNAUTHORIZED",
    "USER_NOT_FOUND",
    "VERSION_NOT_FOUND",
    "WORKFLOW_NOT_FOUND",
]
