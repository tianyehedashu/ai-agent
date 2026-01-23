"""
SQLAlchemy User Repository - 用户仓储实现

使用 SQLAlchemy 实现用户数据访问
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.domain.repositories.user_repository import UserRepository
from domains.identity.infrastructure.models.user import User


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

    async def get_by_email(self, email: str) -> User | None:
        """通过邮箱获取用户"""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update(
        self,
        user_id: uuid.UUID,
        name: str | None = None,
        avatar_url: str | None = None,
        hashed_password: str | None = None,
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

        await self.db.flush()
        await self.db.refresh(user)
        return user
