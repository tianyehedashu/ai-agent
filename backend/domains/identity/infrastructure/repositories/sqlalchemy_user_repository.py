"""
SQLAlchemy User Repository - 用户仓储实现

使用 SQLAlchemy 实现用户数据访问
"""

from collections.abc import Sequence
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from domains.identity.domain.policies.platform_role_policy import ANONYMOUS_ROLE
from domains.identity.domain.repositories.user_repository import UserListFilters, UserRepository
from domains.identity.infrastructure.models.user import User


def _apply_user_list_filters(
    stmt: Select[tuple[User]], filters: UserListFilters
) -> Select[tuple[User]]:
    if filters.exclude_anonymous:
        stmt = stmt.where(User.role != ANONYMOUS_ROLE)
    if filters.role is not None:
        stmt = stmt.where(User.role == filters.role)
    if filters.is_active is not None:
        stmt = stmt.where(User.is_active == filters.is_active)
    if filters.search:
        needle = filters.search.strip().lower()
        if needle:
            pattern = f"%{needle}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.email).like(pattern),
                    func.lower(User.name).like(pattern),
                )
            )
    return stmt


class SQLAlchemyUserRepository(UserRepository):
    """SQLAlchemy 用户仓储实现"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        email: str,
        hashed_password: str,
        name: str,
        role: str = "user",
        is_active: bool = True,
    ) -> User:
        """创建用户"""
        user = User(
            email=email,
            hashed_password=hashed_password,
            name=name,
            role=role,
            is_active=is_active,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """通过 ID 获取用户"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def list_by_ids(self, user_ids: Sequence[uuid.UUID]) -> list[User]:
        """批量按 ID 获取用户"""
        if not user_ids:
            return []
        result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
        return list(result.scalars().all())

    async def get_by_email(self, email: str) -> User | None:
        """通过邮箱获取用户"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_email_insensitive(self, email: str) -> User | None:
        """通过邮箱获取用户（不区分大小写）"""
        normalized = email.strip().lower()
        result = await self.db.execute(select(User).where(func.lower(User.email) == normalized))
        return result.scalar_one_or_none()

    async def update(
        self,
        user_id: uuid.UUID,
        name: str | None = None,
        avatar_url: str | None = None,
        hashed_password: str | None = None,
        vendor_creator_id: int | None = None,
        *,
        update_vendor_creator_id: bool = False,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        """更新用户"""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        if name is not None:
            user.name = name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if hashed_password is not None:
            user.hashed_password = hashed_password
        if update_vendor_creator_id:
            user.vendor_creator_id = vendor_creator_id
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        filters: UserListFilters,
    ) -> list[User]:
        """分页列出用户（按 created_at 降序）。"""
        stmt = _apply_user_list_filters(select(User), filters)
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(self, filters: UserListFilters) -> int:
        """统计符合筛选条件的用户数。"""
        stmt = _apply_user_list_filters(select(func.count(User.id)), filters)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def count_all(self) -> int:
        """统计用户总数"""
        result = await self.db.execute(select(func.count(User.id)))
        return result.scalar() or 0

    async def count_by_role(self, role: str) -> int:
        """统计指定平台角色的用户数"""
        result = await self.db.execute(select(func.count(User.id)).where(User.role == role))
        return result.scalar() or 0

    async def list_by_roles(
        self,
        roles: Sequence[str],
        *,
        limit: int = 100,
    ) -> list[User]:
        """按平台角色列表查询用户"""
        if not roles:
            return []
        result = await self.db.execute(select(User).where(User.role.in_(roles)).limit(limit))
        return list(result.scalars().all())
