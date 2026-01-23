"""
RBAC Infrastructure Adapter - RBAC 基础设施适配器

提供 FastAPI 框架适配：
- FastAPI 装饰器
- 中间件实现
"""

from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import HTTPException, status

from domains.identity.domain.rbac import (
    Permission,
    has_permission,
)


def require_permission(permission: Permission):
    """
    权限要求装饰器（FastAPI 适配）

    用于 FastAPI 路由

    Args:
        permission: 所需权限
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, current_user: dict | None = None, **kwargs):
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            user_role = current_user.get("role", "user")

            if not has_permission(user_role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}",
                )

            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


class RBACMiddleware:
    """
    RBAC 中间件（FastAPI 适配）

    可选：用于更细粒度的权限控制
    """

    def __init__(self, required_permissions: list[Permission] | None = None):
        self.required_permissions = required_permissions or []

    async def __call__(
        self,
        current_user: dict[str, Any],
    ) -> bool:
        """检查权限"""
        user_role = current_user.get("role", "user")

        for permission in self.required_permissions:
            if not has_permission(user_role, permission):
                return False

        return True
