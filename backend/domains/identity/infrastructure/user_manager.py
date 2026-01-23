"""
User Manager - 用户管理器

提供 FastAPI Users 的用户管理器实现
"""

import uuid

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin

from bootstrap.config import settings
from domains.identity.infrastructure.models.user import User


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """用户管理器"""

    reset_password_token_secret = settings.jwt_secret_key
    verification_token_secret = settings.jwt_secret_key

    async def on_after_register(
        self,
        user: User,
        request: Request | None = None,
    ) -> None:
        """用户注册后的回调"""
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(
        self,
        user: User,
        token: str,
        request: Request | None = None,
    ) -> None:
        """忘记密码后的回调"""
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(
        self,
        user: User,
        token: str,
        request: Request | None = None,
    ) -> None:
        """请求验证后的回调"""
        print(f"Verification requested for user {user.id}. Verification token: {token}")
