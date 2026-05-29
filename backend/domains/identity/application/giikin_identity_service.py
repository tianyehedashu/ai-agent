"""giikin SSO 身份 JIT 映射服务。

SSO 模式下，HiGress 注入的 giikin 用户首次访问时按 ``giikin_user_id`` 即时创建
（Just-In-Time）本地用户，并复用默认 personal team 开通逻辑；后续访问直接命中。
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from domains.identity.domain.services.password_service import PasswordService
from domains.identity.infrastructure.default_tenant_lifecycle import (
    provision_default_tenant_for_new_user,
)
from domains.identity.infrastructure.repositories import SQLAlchemyUserRepository
from libs.iam.deps import get_default_tenant_provisioner
from utils.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.identity.domain.repositories.user_repository import UserEntity, UserRepository
    from domains.identity.infrastructure.auth.giikin_gateway import GiikinGatewayClaims
    from libs.iam.tenancy import DefaultTenantProvisionerPort

logger = get_logger(__name__)

# 合成邮箱后缀：giikin SSO 用户在本地的占位邮箱（不可用于登录）
GIIKIN_EMAIL_SUFFIX = "@giikin.sso"


class GiikinIdentityService:
    """按 giikin SSO 身份解析/创建本地用户。"""

    def __init__(
        self,
        db: AsyncSession,
        *,
        user_repo: UserRepository | None = None,
        tenant_provisioner: DefaultTenantProvisionerPort | None = None,
    ) -> None:
        self.db = db
        self.user_repo = user_repo or SQLAlchemyUserRepository(db)
        self._tenant_provisioner = tenant_provisioner
        self._password_service = PasswordService()

    def _tenant_provisioner_or_default(self) -> DefaultTenantProvisionerPort:
        return self._tenant_provisioner or get_default_tenant_provisioner()

    async def resolve_or_provision(self, claims: GiikinGatewayClaims) -> UserEntity:
        """按 giikin user_id 查本地用户；不存在则 JIT 创建并开通 personal team。"""
        existing = await self.user_repo.get_by_giikin_user_id(claims.user_id)
        if existing is not None:
            return existing

        email = f"giikin-{claims.user_id}{GIIKIN_EMAIL_SUFFIX}"
        # 不可用随机密码：SSO 用户不走本地密码登录
        unusable_password = self._password_service.hash(secrets.token_urlsafe(32))

        user = await self.user_repo.create(
            email=email,
            hashed_password=unusable_password,
            name=claims.name,
            role="user",
            giikin_user_id=claims.user_id,
        )

        await provision_default_tenant_for_new_user(
            session=self.db,
            provisioner=self._tenant_provisioner_or_default(),
            user_id=user.id,
            display_name=claims.name,
            log=logger,
        )

        logger.info("JIT provisioned giikin user %s -> local %s", claims.user_id, user.id)
        return user


__all__ = ["GiikinIdentityService"]
