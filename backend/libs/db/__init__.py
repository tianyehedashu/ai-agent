"""
Database Module

提供数据库相关的基础设施：
- database: 数据库连接和会话管理
- permission_context: 数据权限上下文
- base_repository: 带所有权过滤的 Repository 基类
"""

from libs.db.base_repository import OwnedRepositoryBase
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    get_permission_context,
    set_permission_context,
)

__all__ = [
    "OwnedRepositoryBase",
    "PermissionContext",
    "clear_permission_context",
    "get_permission_context",
    "set_permission_context",
]
