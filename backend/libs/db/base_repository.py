"""
Base Repository - Repository 基类

提供多租户（tenant_id）与用户归属（user_id）过滤的 Repository 基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import uuid
import warnings

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from libs.db.data_scope import DataScopeEnforcer, require_permission_context
from libs.db.permission_context import get_permission_context

T = TypeVar("T")


def _model_has_tenant_id(model: type[object]) -> bool:
    return hasattr(model, "tenant_id")


class OwnedRepositoryBase(ABC, Generic[T]):
    """带所有权过滤的 Repository 基类（历史通用基类）。

    模型已使用 ``TenantScopedMixin``（``tenant_id``）时，应改用
    ``TenantScopedRepositoryBase``；本类仍支持 ``user_id`` / 匿名列回落。

    自动根据 PermissionContext 过滤数据：
    - 管理员：可访问所有数据
    - 普通用户：只能访问自己的数据
    - 无上下文：返回空结果（安全默认）

    子类需要实现：
    - model_class: 返回模型类
    - anonymous_user_id_column: 如果支持匿名用户，返回字段名

    Example:
        from domains.session.domain.interfaces import (
            SessionRepositoryInterface,
        )

        class SessionRepository(OwnedRepositoryBase[Session], SessionRepositoryInterface):
            @property
            def model_class(self) -> type[Session]:
                return Session

            @property
            def anonymous_user_id_column(self) -> str:
                return "anonymous_user_id"
    """

    _owned_tenant_scope_warned: bool = False

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        if not type(self)._owned_tenant_scope_warned and _model_has_tenant_id(self.model_class):
            type(self)._owned_tenant_scope_warned = True
            warnings.warn(
                f"{type(self).__name__} uses OwnedRepositoryBase with a tenant-scoped model; "
                "prefer TenantScopedRepositoryBase (see libs.db.base_repository).",
                DeprecationWarning,
                stacklevel=2,
            )

    @property
    @abstractmethod
    def model_class(self) -> type[T]:
        """返回模型类"""
        ...

    @property
    def user_id_column(self) -> str:
        """用户 ID 字段名，子类可覆盖"""
        return "user_id"

    @property
    def anonymous_user_id_column(self) -> str | None:
        """匿名用户 ID 字段名，不支持匿名则返回 None"""
        return None

    def _apply_ownership_filter(self, query: Select) -> Select:
        """应用数据作用域过滤（优先 tenant_id，否则 user_id / anonymous）。"""
        ctx = get_permission_context()
        if ctx is None:
            return query.where(False)  # type: ignore[arg-type]

        if ctx.is_admin:
            return query

        model = self.model_class

        if _model_has_tenant_id(model):
            return DataScopeEnforcer.apply_to_query(query, model)

        if ctx.is_anonymous and self.anonymous_user_id_column:
            return query.where(
                getattr(model, self.anonymous_user_id_column) == ctx.anonymous_user_id
            )
        if ctx.user_id:
            return query.where(getattr(model, self.user_id_column) == ctx.user_id)

        return query.where(False)  # type: ignore[arg-type]

    async def find_owned(
        self,
        skip: int = 0,
        limit: int = 20,
        order_by: str | None = None,
        order_desc: bool = True,
        **filters,
    ) -> list[T]:
        """查询当前用户拥有的数据（自动过滤）

        Args:
            skip: 跳过记录数
            limit: 返回记录数
            order_by: 排序字段名
            order_desc: 是否降序
            **filters: 额外过滤条件

        Returns:
            实体列表
        """
        query = select(self.model_class)
        query = self._apply_ownership_filter(query)

        # 应用额外过滤条件
        for field, value in filters.items():
            if value is not None:
                query = query.where(getattr(self.model_class, field) == value)

        # 应用排序
        if order_by and hasattr(self.model_class, order_by):
            order_column = getattr(self.model_class, order_by)
            if order_desc:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_owned(self, entity_id: uuid.UUID) -> T | None:
        """获取单个实体（自动检查所有权）

        Args:
            entity_id: 实体 ID

        Returns:
            实体或 None（如果不存在或无权限）
        """
        query = select(self.model_class).where(self.model_class.id == entity_id)
        query = self._apply_ownership_filter(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def count_owned(self, **filters) -> int:
        """统计当前用户拥有的数据数量

        Args:
            **filters: 额外过滤条件

        Returns:
            数量
        """
        query = select(func.count()).select_from(self.model_class)
        query = self._apply_ownership_filter(query)

        # 应用额外过滤条件
        for field, value in filters.items():
            if value is not None:
                query = query.where(getattr(self.model_class, field) == value)

        result = await self.db.execute(query)
        return result.scalar() or 0


class TenantScopedRepositoryBase(ABC, Generic[T]):
    """多租户仓储基类（要求 model 暴露 tenant_id）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @property
    @abstractmethod
    def model_class(self) -> type[T]:
        ...

    def _apply_tenant_scope(self, query: Select) -> Select:
        require_permission_context()
        return DataScopeEnforcer.apply_to_query(query, self.model_class)

    async def find_for_tenants(
        self,
        skip: int = 0,
        limit: int = 20,
        order_by: str | None = None,
        order_desc: bool = True,
        **filters: object,
    ) -> list[T]:
        query = select(self.model_class)
        query = self._apply_tenant_scope(query)
        for field, value in filters.items():
            if value is not None:
                query = query.where(getattr(self.model_class, field) == value)
        if order_by and hasattr(self.model_class, order_by):
            order_column = getattr(self.model_class, order_by)
            query = query.order_by(
                order_column.desc() if order_desc else order_column.asc()
            )
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_in_tenants(self, entity_id: uuid.UUID) -> T | None:
        query = select(self.model_class).where(self.model_class.id == entity_id)
        query = self._apply_tenant_scope(query)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def count_for_tenants(self, **filters: object) -> int:
        query = select(func.count()).select_from(self.model_class)
        query = self._apply_tenant_scope(query)
        for field, value in filters.items():
            if value is not None:
                query = query.where(getattr(self.model_class, field) == value)
        result = await self.db.execute(query)
        return int(result.scalar() or 0)


__all__ = ["OwnedRepositoryBase", "TenantScopedRepositoryBase"]
