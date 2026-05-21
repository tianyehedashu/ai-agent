"""DataScope SQL 适配：将 IAM 策略落实为 SQLAlchemy where 子句。"""

from __future__ import annotations

from sqlalchemy.sql import ColumnElement, Select

from libs.iam.data_scope_policy import resolve_team_ids_for_context
from libs.iam.permission_context import PermissionContext, get_permission_context


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


__all__ = ["DataScopeEnforcer"]
