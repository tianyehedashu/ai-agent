"""DataScope：多租户行级可见性（Casbin 风格机制层，不含 domain 业务规则）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import uuid

from sqlalchemy.sql import ColumnElement, Select

from libs.db.permission_context import PermissionContext, get_permission_context


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


class DataScopeEnforcer:
    """按 tenant_id 过滤多租户表（Subject 经 team_members 解析为 team_ids）。"""

    @staticmethod
    def tenant_column(model: type[object]) -> ColumnElement[object]:
        col = getattr(model, "tenant_id", None)
        if col is None:
            msg = f"{model!r} has no tenant_id (TenantScopedMixin required)"
            raise TypeError(msg)
        return col  # type: ignore[return-value]

    @classmethod
    def visibility_clause(cls, model: type[object], ctx: PermissionContext | None = None):
        """生成 ``tenant_id IN team_ids`` 子句；admin 返回 None（不过滤）。"""
        permission = ctx if ctx is not None else get_permission_context()
        if permission is None:
            return cls.tenant_column(model).in_(())  # type: ignore[attr-defined]

        if permission.is_admin:
            return None

        team_ids = resolve_team_ids_for_context(permission)
        if not team_ids:
            return cls.tenant_column(model).in_(())  # type: ignore[attr-defined]

        return cls.tenant_column(model).in_(team_ids)  # type: ignore[attr-defined]

    @classmethod
    def apply_to_query(cls, query: Select, model: type[object]) -> Select:
        clause = cls.visibility_clause(model)
        if clause is None:
            return query
        return query.where(clause)


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
    "DataScopeEnforcer",
    "enforce_data_scope",
    "require_permission_context",
    "resolve_team_ids_for_context",
]
