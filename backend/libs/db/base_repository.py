"""
Base Repository - Repository 基类

提供多租户（tenant_id）过滤的 Repository 基类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from libs.db.data_scope_clause import DataScopeEnforcer
from libs.iam.data_scope_policy import require_permission_context

T = TypeVar("T")


class TenantScopedRepositoryBase(ABC, Generic[T]):
    """多租户仓储基类（要求 model 暴露 tenant_id）。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @property
    @abstractmethod
    def model_class(self) -> type[T]: ...

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
            query = query.order_by(order_column.desc() if order_desc else order_column.asc())
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


__all__ = ["TenantScopedRepositoryBase"]
