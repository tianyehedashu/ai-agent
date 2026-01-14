"""
User Service - 用户服务

提供用户的认证、管理功能。
"""

from datetime import UTC, datetime, timedelta
import uuid

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from exceptions import AuthenticationError, NotFoundError, TokenError
from models.user import User


class TokenPair:
    """Token 对"""

    def __init__(
        self,
        access_token: str,
        expires_in: int,
        refresh_token: str | None = None,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in


class UserService:
    """用户服务

    管理用户的创建、认证、Token 生成等功能。

    Attributes:
        db: 数据库会话
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        email: str,
        password: str,
        name: str,
    ) -> User:
        """创建用户

        Args:
            email: 邮箱地址
            password: 明文密码
            name: 用户名

        Returns:
            创建的用户对象
        """
        password_hash = self._hash_password(password)

        user = User(
            email=email,
            password_hash=password_hash,
            name=name,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def get_by_email(self, email: str) -> User | None:
        """通过邮箱获取用户

        Args:
            email: 邮箱地址

        Returns:
            用户对象或 None
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        """通过 ID 获取用户

        Args:
            user_id: 用户 ID

        Returns:
            用户对象或 None
        """
        result = await self.db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, user_id: str) -> User:
        """通过 ID 获取用户，不存在则抛出异常

        Args:
            user_id: 用户 ID

        Returns:
            用户对象

        Raises:
            NotFoundError: 用户不存在时
        """
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        """验证用户凭据

        Args:
            email: 邮箱地址
            password: 明文密码

        Returns:
            验证成功的用户对象

        Raises:
            AuthenticationError: 认证失败时
        """
        user = await self.get_by_email(email)
        if not user:
            raise AuthenticationError("Invalid email or password")

        if not self._verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        return user

    async def update(
        self,
        user_id: str,
        name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        """更新用户信息

        Args:
            user_id: 用户 ID
            name: 新用户名（可选）
            avatar_url: 新头像 URL（可选）

        Returns:
            更新后的用户对象

        Raises:
            NotFoundError: 用户不存在时
        """
        user = await self.get_by_id_or_raise(user_id)

        if name is not None:
            user.name = name
        if avatar_url is not None:
            user.avatar_url = avatar_url

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def verify_password(self, user_id: str, password: str) -> bool:
        """验证用户密码

        Args:
            user_id: 用户 ID
            password: 待验证的密码

        Returns:
            密码是否正确
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False
        return self._verify_password(password, user.password_hash)

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
    ) -> None:
        """修改用户密码

        Args:
            user_id: 用户 ID
            old_password: 旧密码
            new_password: 新密码

        Raises:
            NotFoundError: 用户不存在时
            AuthenticationError: 旧密码验证失败时
        """
        user = await self.get_by_id_or_raise(user_id)

        if not self._verify_password(old_password, user.password_hash):
            raise AuthenticationError("Invalid current password")

        user.password_hash = self._hash_password(new_password)
        await self.db.flush()

    async def create_token(self, user: User) -> TokenPair:
        """创建 Token 对

        Args:
            user: 用户对象

        Returns:
            包含 access_token 和 expires_in 的 TokenPair
        """
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=settings.jwt_expire_hours)

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "iat": now,
            "exp": expires_at,
        }

        access_token = jwt.encode(
            payload,
            settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

        return TokenPair(
            access_token=access_token,
            expires_in=settings.jwt_expire_hours * 3600,
        )

    async def get_user_from_token(self, token: str) -> User | None:
        """从 Token 获取用户

        Args:
            token: JWT Token

        Returns:
            用户对象或 None
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )
            user_id = payload.get("sub")
            if not user_id:
                return None
            return await self.get_by_id(user_id)
        except jwt.ExpiredSignatureError:
            return None
        except jwt.PyJWTError:
            return None

    async def refresh_token(self, refresh_token: str) -> TokenPair:
        """刷新 Token

        Args:
            refresh_token: 刷新 Token

        Returns:
            新的 TokenPair

        Raises:
            TokenError: Token 无效时
        """
        user = await self.get_user_from_token(refresh_token)
        if not user:
            raise TokenError("Invalid refresh token")
        return await self.create_token(user)

    def _hash_password(self, password: str) -> str:
        """哈希密码"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), hashed.encode())
