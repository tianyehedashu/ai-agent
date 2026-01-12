"""
User Service - 用户服务
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt
from pydantic import BaseModel
from sqlalchemy import select

from app.config import settings
from db.database import get_session_context
from models.user import User


class TokenPair(BaseModel):
    """Token 对"""

    access_token: str
    refresh_token: str | None = None
    expires_in: int


class UserService:
    """用户服务"""

    async def create(
        self,
        email: str,
        password: str,
        name: str,
    ) -> User:
        """创建用户"""
        password_hash = self._hash_password(password)

        async with get_session_context() as session:
            user = User(
                email=email,
                password_hash=password_hash,
                name=name,
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)
            return user

    async def get_by_email(self, email: str) -> User | None:
        """通过邮箱获取用户"""
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()

    async def get_by_id(self, user_id: str) -> User | None:
        """通过 ID 获取用户"""
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.id == uuid.UUID(user_id))
            )
            return result.scalar_one_or_none()

    async def authenticate(self, email: str, password: str) -> User | None:
        """验证用户"""
        user = await self.get_by_email(email)
        if not user:
            return None

        if not self._verify_password(password, user.password_hash):
            return None

        return user

    async def update(self, user_id: str, data: dict[str, Any]) -> User:
        """更新用户"""
        async with get_session_context() as session:
            result = await session.execute(
                select(User).where(User.id == uuid.UUID(user_id))
            )
            user = result.scalar_one_or_none()
            if not user:
                raise ValueError("User not found")

            for key, value in data.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            await session.flush()
            await session.refresh(user)
            return user

    async def verify_password(self, user_id: str, password: str) -> bool:
        """验证密码"""
        user = await self.get_by_id(user_id)
        if not user:
            return False
        return self._verify_password(password, user.password_hash)

    async def change_password(self, user_id: str, new_password: str) -> None:
        """修改密码"""
        password_hash = self._hash_password(new_password)
        await self.update(user_id, {"password_hash": password_hash})

    async def create_token(self, user: User) -> TokenPair:
        """创建 Token"""
        now = datetime.utcnow()
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
        """从 Token 获取用户"""
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
        except jwt.PyJWTError:
            return None

    async def refresh_token(self, refresh_token: str) -> TokenPair:
        """刷新 Token"""
        user = await self.get_user_from_token(refresh_token)
        if not user:
            raise ValueError("Invalid refresh token")
        return await self.create_token(user)

    def _hash_password(self, password: str) -> str:
        """哈希密码"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode(), salt).decode()

    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), hashed.encode())
