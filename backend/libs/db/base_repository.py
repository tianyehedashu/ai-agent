"""
Base Repository - Repository 基类

提供带所有权过滤的 Repository 基类，自动根据 PermissionContext 过滤数据。
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from libs.db.permission_context import get_permission_context

T = TypeVar("T")  # 实体类型（OwnedMixin 用于类型检查）


class OwnedRepositoryBase(ABC, Generic[T]):
    """带所有权过滤的 Repository 基类

    自动根据 PermissionContext 过滤数据：
    - 管理员：可访问所有数据
    - 普通用户：只能访问自己的数据
    - 无上下文：返回空结果（安全默认）

    子类需要实现：
    - model_class: 返回模型类
    - anonymous_user_id_column: 如果支持匿名用户，返回字段名

    Example:
        from domains.agent.domain.interfaces.session_repository import (
            SessionRepository as SessionRepositoryInterface,
        )

        class SessionRepository(OwnedRepositoryBase[Session], SessionRepositoryInterface):
            @property
            def model_class(self) -> type[Session]:
                return Session

            @property
            def anonymous_user_id_column(self) -> str:
                return "anonymous_user_id"
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
        """应用所有权过滤

        - 管理员：不过滤，返回所有数据
        - 普通用户：按 user_id 或 anonymous_user_id 过滤
        - 无上下文：返回空结果（安全默认）
        """
        ctx = get_permission_context()
        if ctx is None:
            # 无上下文时返回空结果（安全默认）
            return query.where(False)  # type: ignore[arg-type]

        if ctx.is_admin:
            # 管理员可访问所有数据
            return query

        model = self.model_class

        if ctx.is_anonymous and self.anonymous_user_id_column:
            # 匿名用户
            return query.where(
                getattr(model, self.anonymous_user_id_column) == ctx.anonymous_user_id
            )
        elif ctx.user_id:
            # 注册用户
            return query.where(getattr(model, self.user_id_column) == ctx.user_id)

        # 无有效身份，返回空结果
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
        query = select(self.model_class).where(
            self.model_class.id == entity_id
        )
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


__all__ = ["OwnedRepositoryBase"]
