"""
Permission Context - 数据权限上下文

提供请求级别的权限上下文，用于 Repository 层的数据过滤。
使用 ContextVar 在请求生命周期内传递权限信息。
"""

from contextvars import ContextVar
from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class PermissionContext:
    """数据权限上下文

    封装当前请求的用户身份和权限信息，用于 Repository 层的数据过滤。

    Attributes:
        user_id: 注册用户 ID（如果是注册用户）
        anonymous_user_id: 匿名用户 ID（如果是匿名用户）
        role: 用户角色（admin, user, viewer）
    """

    user_id: uuid.UUID | None = None
    anonymous_user_id: str | None = None
    role: str = "user"

    @property
    def is_admin(self) -> bool:
        """是否为管理员"""
        return self.role == "admin"

    @property
    def is_anonymous(self) -> bool:
        """是否为匿名用户"""
        return self.anonymous_user_id is not None

    @property
    def has_identity(self) -> bool:
        """是否有有效身份"""
        return self.user_id is not None or self.anonymous_user_id is not None


# 使用 ContextVar 在请求生命周期内传递权限上下文
_permission_context: ContextVar[PermissionContext | None] = ContextVar(
    "permission_context", default=None
)


def get_permission_context() -> PermissionContext | None:
    """获取当前权限上下文"""
    return _permission_context.get()


def set_permission_context(ctx: PermissionContext | None) -> None:
    """设置当前权限上下文"""
    _permission_context.set(ctx)


def clear_permission_context() -> None:
    """清除当前权限上下文"""
    _permission_context.set(None)


__all__ = [
    "PermissionContext",
    "clear_permission_context",
    "get_permission_context",
    "set_permission_context",
]
