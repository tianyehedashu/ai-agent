"""
User Manager - 用户管理器

提供 FastAPI Users 的用户管理器实现。
包含登录/注册后的回调钩子，用于幂等开通 personal team。
"""

import uuid

from fastapi import Request, Response
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from bootstrap.config import settings
from domains.identity.infrastructure.default_tenant_lifecycle import (
    provision_default_tenant_for_new_user,
)
from domains.identity.infrastructure.models.user import User
from libs.iam.deps import get_default_tenant_provisioner
from libs.iam.tenancy import DefaultTenantProvisionerPort
from utils.logging import get_logger

logger = get_logger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """用户管理器"""

    reset_password_token_secret = settings.jwt_secret_key
    verification_token_secret = settings.jwt_secret_key

    def __init__(
        self,
        user_db: SQLAlchemyUserDatabase[User, uuid.UUID],
        *,
        tenant_provisioner: DefaultTenantProvisionerPort | None = None,
    ) -> None:
        super().__init__(user_db)
        self._tenant_provisioner = tenant_provisioner

    def _tenant_provisioner_or_default(self) -> DefaultTenantProvisionerPort:
        return self._tenant_provisioner or get_default_tenant_provisioner()

    async def on_after_register(
        self,
        user: User,
        request: Request | None = None,
    ) -> None:
        """用户注册后回调：创建 personal team"""
        logger.info("User %s has registered.", user.id)

        await provision_default_tenant_for_new_user(
            session=self.user_db.session,
            provisioner=self._tenant_provisioner_or_default(),
            user_id=user.id,
            display_name=user.name or (user.email.split("@")[0] if user.email else None),
            log=logger,
        )

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response: Response | None = None,
    ) -> None:
        """用户登录后回调：幂等补齐 personal team（存量修复）。"""
        await provision_default_tenant_for_new_user(
            session=self.user_db.session,
            provisioner=self._tenant_provisioner_or_default(),
            user_id=user.id,
            display_name=user.name or (user.email.split("@")[0] if user.email else None),
            log=logger,
        )

    async def on_after_forgot_password(
        self,
        user: User,
        token: str,
        request: Request | None = None,
    ) -> None:
        """忘记密码后的回调"""
        logger.info("User %s has forgot their password. Reset token: %s", user.id, token)

    async def on_after_request_verify(
        self,
        user: User,
        token: str,
        request: Request | None = None,
    ) -> None:
        """请求验证后的回调"""
        logger.info("Verification requested for user %s. Verification token: %s", user.id, token)
