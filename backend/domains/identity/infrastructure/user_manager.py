"""
User Manager - 用户管理器

提供 FastAPI Users 的用户管理器实现。
包含登录/注册后的回调钩子，用于匿名数据迁移。
"""

import uuid

from fastapi import Request, Response
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from bootstrap.config import settings
from domains.identity.application.session_migration_service import (
    migrate_anonymous_data_on_auth,
)
from domains.identity.infrastructure.default_tenant_lifecycle import (
    provision_default_tenant_for_new_user,
)
from domains.identity.infrastructure.models.user import User
from libs.iam.tenancy import DefaultTenantProvisionerPort
from utils.logging import get_logger

logger = get_logger(__name__)

# 匿名用户 Cookie 名称（与 principal_service 保持一致）
_ANONYMOUS_USER_COOKIE = "anonymous_user_id"


def _default_tenant_provisioner() -> DefaultTenantProvisionerPort:
    from domains.gateway.infrastructure.iam.default_tenant_provisioner import (
        GatewayDefaultTenantProvisioner,
    )

    return GatewayDefaultTenantProvisioner()


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
        return self._tenant_provisioner or _default_tenant_provisioner()

    async def _migrate_anonymous_data(
        self,
        user: User,
        request: Request | None,
    ) -> None:
        """迁移当前浏览器的匿名数据到正式账号

        从请求 Cookie 中获取 anonymous_user_id，如果存在则触发数据迁移。
        """
        if request is None:
            return

        anonymous_user_id = request.cookies.get(_ANONYMOUS_USER_COOKIE)
        if not anonymous_user_id:
            return

        db = self.user_db.session
        result = await migrate_anonymous_data_on_auth(db, user.id, anonymous_user_id)
        if result.total > 0:
            logger.info(
                "Post-auth migration for user %s: %d sessions, %d video_tasks",
                user.id,
                result.sessions,
                result.video_tasks,
            )

    async def on_after_register(
        self,
        user: User,
        request: Request | None = None,
    ) -> None:
        """用户注册后回调：创建 personal team + 迁移匿名数据"""
        logger.info("User %s has registered.", user.id)

        await provision_default_tenant_for_new_user(
            session=self.user_db.session,
            provisioner=self._tenant_provisioner_or_default(),
            user_id=user.id,
            display_name=user.name or (user.email.split("@")[0] if user.email else None),
            log=logger,
        )

        await self._migrate_anonymous_data(user, request)

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response: Response | None = None,
    ) -> None:
        """用户登录后回调：迁移匿名数据；幂等补齐 personal team（存量修复）。"""
        await self._migrate_anonymous_data(user, request)
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
