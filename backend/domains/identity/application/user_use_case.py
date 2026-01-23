"""
User Use Case - 用户用例

编排用户相关的操作，包括注册、认证、Token 管理。
"""

import uuid

from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.domain.repositories.user_repository import UserRepository
from domains.identity.domain.services.password_service import PasswordService
from domains.identity.domain.services.token_service import TokenPair, TokenService
from domains.identity.infrastructure.authentication import get_jwt_strategy
from domains.identity.infrastructure.models.user import User
from domains.identity.infrastructure.repositories import SQLAlchemyUserRepository
from domains.identity.infrastructure.user_manager import UserManager
from exceptions import AuthenticationError, NotFoundError


class UserUseCase:
    """用户用例

    协调用户相关的操作，使用领域服务进行业务规则处理。
    """

    def __init__(
        self,
        db: AsyncSession,
        user_repo: UserRepository | None = None,
    ) -> None:
        self.db = db
        self.user_repo = user_repo or SQLAlchemyUserRepository(db)
        self.password_service = PasswordService()
        self.token_service = TokenService()

    # =========================================================================
    # User CRUD
    # =========================================================================

    async def create_user(
        self,
        email: str,
        password: str,
        name: str,
    ) -> User:
        """创建用户

        Args:
            email: 邮箱地址
            password: 明文密码
            name: 用户名称

        Returns:
            创建的用户对象
        """
        hashed_password = self.password_service.hash(password)

        user = await self.user_repo.create(
            email=email,
            hashed_password=hashed_password,
            name=name,
        )

        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        """通过 ID 获取用户"""
        return await self.user_repo.get_by_id(uuid.UUID(user_id))

    async def get_user_by_id_or_raise(self, user_id: str) -> User:
        """通过 ID 获取用户，不存在则抛出异常"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def get_user_by_email(self, email: str) -> User | None:
        """通过邮箱获取用户"""
        return await self.user_repo.get_by_email(email)

    async def update_user(
        self,
        user_id: str,
        name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        """更新用户信息"""
        user = await self.user_repo.update(
            user_id=uuid.UUID(user_id),
            name=name,
            avatar_url=avatar_url,
        )
        if not user:
            raise NotFoundError("User", user_id)
        return user

    # =========================================================================
    # Authentication
    # =========================================================================

    async def authenticate(self, email: str, password: str) -> User:
        """用户认证

        Args:
            email: 邮箱地址
            password: 密码

        Returns:
            认证成功的用户对象

        Raises:
            AuthenticationError: 认证失败时
        """
        user = await self.get_user_by_email(email)
        if not user:
            raise AuthenticationError("Invalid email or password")

        if not self.password_service.verify(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        return user

    async def verify_password(self, user_id: str, password: str) -> bool:
        """验证用户密码"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        return self.password_service.verify(password, user.hashed_password)

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
    ) -> None:
        """修改用户密码"""
        user = await self.get_user_by_id_or_raise(user_id)

        if not self.password_service.verify(old_password, user.hashed_password):
            raise AuthenticationError("Invalid current password")

        new_hashed = self.password_service.hash(new_password)
        await self.user_repo.update(
            user_id=uuid.UUID(user_id),
            hashed_password=new_hashed,
        )

    # =========================================================================
    # Token Management
    # =========================================================================

    async def create_token(self, user: User) -> TokenPair:
        """创建 Token 对"""
        return await self.token_service.create_token_pair(user)

    async def get_user_from_token(self, token: str) -> User | None:
        """从 Token 获取用户"""
        strategy = get_jwt_strategy()
        user_db = SQLAlchemyUserDatabase(self.db, User)
        user_manager = UserManager(user_db)

        user = await strategy.read_token(token, user_manager)
        return user

    async def refresh_token(self, refresh_token: str) -> TokenPair:
        """刷新 Token"""
        payload = self.token_service.verify_refresh_token(refresh_token)
        if not payload:
            raise AuthenticationError("Invalid refresh token")

        user = await self.get_user_by_id(payload.sub)
        if not user:
            raise AuthenticationError("User not found")

        return await self.token_service.create_token_pair(user)
