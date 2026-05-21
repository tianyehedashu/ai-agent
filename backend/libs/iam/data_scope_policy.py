"""DataScope 授权策略：纯函数判定，不依赖 SQLAlchemy。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import uuid

from libs.iam.permission_context import PermissionContext, get_permission_context


class DataAction(str, Enum):
    READ = "read"
    LIST = "list"
    WRITE = "write"
    DELETE = "delete"


@dataclass(frozen=True)
class DataResource:
    """路由侧显式鉴权用的资源描述（Object）。"""

    kind: str
    tenant_id: uuid.UUID | None = None


def require_permission_context() -> PermissionContext:
    ctx = get_permission_context()
    if ctx is None:
        msg = "PermissionContext is required for data scope enforcement"
        raise RuntimeError(msg)
    return ctx


def resolve_team_ids_for_context(ctx: PermissionContext) -> frozenset[uuid.UUID]:
    """返回当前请求可访问的 tenant_id 集合（已解析则直接用 team_ids）。"""
    if ctx.is_admin:
        return frozenset()
    return ctx.team_ids


def enforce_data_scope(
    ctx: PermissionContext,
    resource: DataResource,
    _action: DataAction,
) -> bool:
    """显式判定：资源 tenant 是否在 ctx.team_ids 内（admin 恒 True）。"""
    if ctx.is_admin:
        return True
    if resource.tenant_id is None:
        return False
    return resource.tenant_id in ctx.team_ids


__all__ = [
    "DataAction",
    "DataResource",
    "enforce_data_scope",
    "require_permission_context",
    "resolve_team_ids_for_context",
]
