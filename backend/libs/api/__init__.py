"""API - 共享 API 组件

跨领域共享的 API 组件：
- deps: 数据库和服务工厂依赖
- errors: 错误消息常量

身份认证相关依赖请使用：domains.identity.presentation.deps
"""

from libs.api.deps import (
    DbSession,
    get_agent_service,
    get_chat_service,
    get_checkpoint_service,
    get_db,
    get_memory_service,
    get_session_service,
    get_stats_service,
    get_title_service,
    get_user_service,
)
from libs.api.errors import (
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

__all__ = [
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
    # Database
    "DbSession",
    # Services
    "get_agent_service",
    "get_chat_service",
    "get_checkpoint_service",
    "get_db",
    "get_memory_service",
    "get_session_service",
    "get_stats_service",
    "get_title_service",
    "get_user_service",
]
