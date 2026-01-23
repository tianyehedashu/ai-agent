"""
User Repository Interface - 用户仓储接口

定义用户数据访问的抽象接口"""

from abc import ABC, abstractmethod
from typing import Protocol
import uuid


class UserEntity(Protocol):
    """用户实体协议"""

    id: uuid.UUID
    email: str
    name: str
    hashed_password: str
    role: str
    is_active: bool


class UserRepository(ABC):
    """用户仓储接口"""

    @abstractmethod
    async def create(
        self,
        email: str,
        hashed_password: str,
        name: str,
        role: str = "user",
        is_active: bool = True,
    ) -> UserEntity:
        """创建用户"""
        ...

    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> UserEntity | None:
        """通过 ID 获取用户"""
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> UserEntity | None:
        """通过邮箱获取用户"""
        ...

    @abstractmethod
    async def update(
        self,
        user_id: uuid.UUID,
        name: str | None = None,
        avatar_url: str | None = None,
        hashed_password: str | None = None,
    ) -> UserEntity | None:
        """更新用户"""
        ...
