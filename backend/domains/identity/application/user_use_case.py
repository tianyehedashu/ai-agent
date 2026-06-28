"""
User Use Case - 用户用例

编排用户相关的操作，包括注册、认证、Token 管理。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from domains.identity.application.ports import (
    InviteCandidateRowView,
    UserSummaryView,
)
from domains.identity.application.token_service import TokenPair, TokenService
from domains.identity.domain.policies.platform_role_policy import (
    assert_bootstrap_grant_admin,
    assert_bootstrap_revoke_admin,
    assert_can_change_platform_role,
    assert_emergency_grant_admin,
)
from domains.identity.domain.policies.platform_user_admin_policy import (
    assert_can_admin_manage_user,
    assert_can_set_user_active,
    parse_platform_user_list_role,
)
from domains.identity.domain.rbac import Role
from domains.identity.domain.repositories.user_repository import UserListFilters, UserRepository
from domains.identity.domain.services.password_service import PasswordService
from domains.identity.infrastructure.authentication import get_jwt_strategy
from domains.identity.infrastructure.default_tenant_lifecycle import (
    provision_default_tenant_for_new_user,
)
from domains.identity.infrastructure.models.user import User
from domains.identity.infrastructure.repositories import SQLAlchemyUserRepository
from domains.identity.infrastructure.repositories.user_invite_candidate_repository import (
    UserInviteCandidateRepository,
)
from domains.identity.infrastructure.user_platform_role_lookup import (
    UserPlatformRoleLookupAdapter,
)
from libs.exceptions import AuthenticationError, NotFoundError, ValidationError
from libs.iam.deps import get_default_tenant_provisioner
from libs.iam.tenancy import DefaultTenantProvisionerPort

if TYPE_CHECKING:
    from domains.identity.application.ports import UserPlatformRoleLookupPort
    from libs.api.pagination import PageParams, PaginatedListResponse


@dataclass(frozen=True, slots=True)
class UserSummary:
    """平台用户摘要（管理面，不含敏感字段）。"""

    id: str
    email: str
    name: str | None
    role: str
    is_active: bool
    is_verified: bool
    status: str
    created_at: datetime
    vendor_creator_id: int | None
    avatar_url: str | None = None


def _user_to_summary(user: User) -> UserSummary:
    return UserSummary(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
        status=user.status,
        created_at=user.created_at,
        vendor_creator_id=user.vendor_creator_id,
        avatar_url=user.avatar_url,
    )


class UserUseCase:
    """用户用例

    协调用户相关的操作，使用领域服务进行业务规则处理。
    """

    def __init__(
        self,
        db: AsyncSession,
        user_repo: UserRepository | None = None,
        *,
        tenant_provisioner: DefaultTenantProvisionerPort | None = None,
    ) -> None:
        self.db = db
        self.user_repo = user_repo or SQLAlchemyUserRepository(db)
        self.password_service = PasswordService()
        self.token_service = TokenService()
        self._tenant_provisioner = tenant_provisioner
        self._platform_role_lookup: UserPlatformRoleLookupPort | None = None
        self._invite_candidate_repo: UserInviteCandidateRepository | None = None

    def _tenant_provisioner_or_default(self) -> DefaultTenantProvisionerPort:
        return self._tenant_provisioner or get_default_tenant_provisioner()

    async def count_users(self) -> int:
        """统计用户总数。"""
        return await self.user_repo.count_all()

    # =========================================================================
    # User CRUD
    # =========================================================================

    async def create_user(
        self,
        email: str,
        password: str,
        name: str,
    ) -> User:
        """创建用户并在落库后幂等创建默认 personal team（租户作用域）。

        HTTP 自助注册由 FastAPI Users 处理，走 ``UserManager.on_after_register``；
        本方法用于程序化管理、测试或直接写入用户表等路径。二者均调用
        ``provision_default_tenant_for_new_user``，依赖 ``ensure_personal_team`` 幂等。

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

        await provision_default_tenant_for_new_user(
            session=self.db,
            provisioner=self._tenant_provisioner_or_default(),
            user_id=user.id,
            display_name=name or (email.split("@")[0] if email else None),
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
        vendor_creator_id: int | None = None,
    ) -> User:
        """更新用户信息"""
        user = await self.user_repo.update(
            user_id=uuid.UUID(user_id),
            name=name,
            avatar_url=avatar_url,
            vendor_creator_id=vendor_creator_id,
        )
        if not user:
            raise NotFoundError("User", user_id)
        return user

    async def lookup_user_by_email(self, email: str) -> UserSummary:
        """按邮箱查找用户（平台管理面，不区分大小写）。"""
        user = await self.user_repo.get_by_email_insensitive(email)
        if user is None:
            raise NotFoundError("User", email.strip())
        return _user_to_summary(user)

    async def lookup_admin_user_by_email(self, *, actor_role: str, email: str) -> UserSummary:
        """平台管理员按邮箱查找可管理用户。"""
        user = await self.user_repo.get_by_email_insensitive(email)
        if user is None:
            raise NotFoundError("User", email.strip())
        assert_can_admin_manage_user(actor_role=actor_role, target_current_role=user.role)
        return _user_to_summary(user)

    async def get_user_summary(self, user_id: str) -> UserSummary:
        """按 ID 获取平台用户摘要（管理面）。"""
        user = await self.get_user_by_id_or_raise(user_id)
        return _user_to_summary(user)

    async def get_admin_user_summary(self, *, actor_role: str, user_id: str) -> UserSummary:
        """平台管理员获取可管理用户摘要。"""
        user = await self.get_user_by_id_or_raise(user_id)
        assert_can_admin_manage_user(actor_role=actor_role, target_current_role=user.role)
        return _user_to_summary(user)

    async def list_users_page(
        self,
        page_params: PageParams,
        filters: UserListFilters,
    ) -> PaginatedListResponse[UserSummary]:
        """分页列出平台用户（默认排除 anonymous）。"""
        from libs.api.pagination import build_page

        role_filter = parse_platform_user_list_role(filters.role)
        normalized_filters = UserListFilters(
            search=filters.search,
            role=role_filter,
            is_active=filters.is_active,
            exclude_anonymous=filters.exclude_anonymous,
        )

        total = await self.user_repo.count_filtered(normalized_filters)
        users = await self.user_repo.list_page(
            offset=page_params.offset,
            limit=page_params.page_size,
            filters=normalized_filters,
        )
        return build_page(
            items=[_user_to_summary(user) for user in users],
            total=total,
            page=page_params.page,
            page_size=page_params.page_size,
        )

    async def admin_update_user(
        self,
        *,
        actor_id: str,
        actor_role: str,
        target_user_id: str,
        name: str | None = None,
        avatar_url: str | None = None,
        vendor_creator_id: int | None = None,
        update_vendor_creator_id: bool = False,
        is_active: bool | None = None,
    ) -> UserSummary:
        """平台管理员更新用户资料与启用状态。"""
        target = await self.get_user_by_id_or_raise(target_user_id)
        assert_can_admin_manage_user(actor_role=actor_role, target_current_role=target.role)

        if (
            name is None
            and avatar_url is None
            and not update_vendor_creator_id
            and is_active is None
        ):
            raise ValidationError("At least one field must be provided")

        if is_active is not None:
            assert_can_set_user_active(
                actor_id=uuid.UUID(actor_id),
                target_id=uuid.UUID(target_user_id),
                new_active=is_active,
            )

        updated = await self.user_repo.update(
            uuid.UUID(target_user_id),
            name=name,
            avatar_url=avatar_url,
            vendor_creator_id=vendor_creator_id,
            update_vendor_creator_id=update_vendor_creator_id,
            is_active=is_active,
        )
        if updated is None:
            raise NotFoundError("User", target_user_id)
        return _user_to_summary(updated)

    async def list_summaries_by_ids(
        self, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, UserSummary]:
        """按 ID 批量返回用户摘要（不含敏感字段）。"""
        if not user_ids:
            return {}
        users = await self.user_repo.list_by_ids(user_ids)
        return {user.id: _user_to_summary(user) for user in users}

    async def list_summary_views_by_ids(
        self, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, UserSummaryView]:
        """``UserSummaryQueryPort``：跨域批量摘要（不含敏感字段）。"""
        summaries = await self.list_summaries_by_ids(user_ids)
        return {
            uid: UserSummaryView(name=summary.name, email=summary.email)
            for uid, summary in summaries.items()
        }

    def _platform_role_lookup_impl(self) -> UserPlatformRoleLookupPort:
        if self._platform_role_lookup is None:
            self._platform_role_lookup = UserPlatformRoleLookupAdapter(self.db)
        return self._platform_role_lookup

    async def roles_by_user_ids(self, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        """``UserPlatformRoleLookupPort``：批量解析平台 role。"""
        return await self._platform_role_lookup_impl().roles_by_user_ids(user_ids)

    def _invite_candidate_repo_impl(self) -> UserInviteCandidateRepository:
        if self._invite_candidate_repo is None:
            self._invite_candidate_repo = UserInviteCandidateRepository(self.db)
        return self._invite_candidate_repo

    async def list_team_invite_candidates_page(
        self,
        page: PageParams,
        *,
        team_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        scope: str,
        search: str | None = None,
    ) -> PaginatedListResponse[InviteCandidateRowView]:
        """``TeamInviteCandidateQueryPort``：团队可邀请用户分页列表。"""
        from libs.api.pagination import build_page

        trimmed_search = search.strip() if search else None
        if trimmed_search == "":
            trimmed_search = None
        repo = self._invite_candidate_repo_impl()
        total = await repo.count(
            team_id=team_id,
            actor_user_id=actor_user_id,
            scope=scope,
            search=trimmed_search,
        )
        rows = await repo.list_page(
            team_id=team_id,
            actor_user_id=actor_user_id,
            scope=scope,
            search=trimmed_search,
            offset=page.offset,
            limit=page.page_size,
        )
        return build_page(
            items=[
                InviteCandidateRowView(id=row.id, email=row.email, name=row.name) for row in rows
            ],
            total=total,
            page=page.page,
            page_size=page.page_size,
        )

    async def bootstrap_set_admin_by_email(
        self, email: str, *, revoke: bool = False, force: bool = False
    ) -> UserSummary:
        """CLI/bootstrap：首个 admin 授权、应急提权（--force）或多人时撤销 admin。"""
        user = await self.user_repo.get_by_email_insensitive(email)
        if user is None:
            raise NotFoundError("User", email.strip())

        admin_count = await self.user_repo.count_by_role(Role.ADMIN.value)
        if revoke:
            assert_bootstrap_revoke_admin(
                target_current_role=user.role,
                admin_count=admin_count,
            )
            new_role = Role.USER.value
        elif force:
            assert_emergency_grant_admin(target_current_role=user.role)
            new_role = Role.ADMIN.value
        else:
            assert_bootstrap_grant_admin(
                target_current_role=user.role,
                admin_count=admin_count,
            )
            new_role = Role.ADMIN.value

        updated = await self.user_repo.update(user.id, role=new_role)
        if updated is None:
            raise NotFoundError("User", str(user.id))
        return _user_to_summary(updated)

    async def set_platform_role(
        self,
        *,
        actor_id: str,
        actor_role: str,
        target_user_id: str,
        new_role: str,
    ) -> UserSummary:
        """设置目标用户的平台角色（仅平台 admin）。"""
        target_uuid = uuid.UUID(target_user_id)
        target = await self.get_user_by_id_or_raise(target_user_id)
        admin_count: int | None = None
        if target.role == Role.ADMIN.value and new_role != Role.ADMIN.value:
            admin_count = await self.user_repo.count_by_role(Role.ADMIN.value)

        assert_can_change_platform_role(
            actor_role=actor_role,
            actor_id=uuid.UUID(actor_id),
            target_id=target_uuid,
            target_current_role=target.role,
            new_role=new_role,
            admin_count=admin_count,
        )

        updated = await self.user_repo.update(target_uuid, role=new_role)
        if updated is None:
            raise NotFoundError("User", target_user_id)
        return _user_to_summary(updated)

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
        from domains.identity.infrastructure.user_manager import UserManager

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
