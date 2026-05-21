"""
Database Module

提供数据库相关的基础设施：
- database: 数据库连接和会话管理
- permission_context: 数据权限上下文
- base_repository: 多租户 Repository 基类
"""

from libs.db.base_repository import TenantScopedRepositoryBase
from libs.db.data_scope_clause import DataScopeEnforcer
from libs.iam.data_scope_policy import DataAction, DataResource, enforce_data_scope
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    get_permission_context,
    set_permission_context,
)

__all__ = [
    "DataAction",
    "DataResource",
    "DataScopeEnforcer",
    "PermissionContext",
    "TenantScopedRepositoryBase",
    "clear_permission_context",
    "enforce_data_scope",
    "get_permission_context",
    "set_permission_context",
]
