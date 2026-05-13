"""
Permission Context - 数据权限上下文

提供请求级别的权限上下文，用于 Repository 层的数据过滤。
使用 ContextVar 在请求生命周期内传递权限信息。
"""

from contextvars import ContextVar
from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class PermissionContext:
    """数据权限上下文

    封装当前请求的用户身份和权限信息，用于 Repository 层的数据过滤。

    Attributes:
        user_id: 注册用户 ID（如果是注册用户）
        anonymous_user_id: 匿名用户 ID（如果是匿名用户）
        role: 用户角色（admin, user, viewer）
        team_id: 当前 **工作区租户**（Tenancy ``Team.id``），通常由 ``X-Team-Id`` 与
            ``TenancyManagementTeamResolveUseCase`` 写入；可为 **personal**（``kind=personal``）
            或 **shared** 团队。内部 Gateway 桥接的计费 ``team_id`` 可与本字段对齐
            （见 ``domains.gateway.application.bridge_attribution``）。**非**管理面 ``usage_aggregation`` 枚举。
        team_role: 当前团队角色（owner/admin/member），仅 team_id 非空时有意义
    """

    user_id: uuid.UUID | None = None
    anonymous_user_id: str | None = None
    role: str = "user"
    team_id: uuid.UUID | None = None
    team_role: str | None = None

    @property
    def is_admin(self) -> bool:
        """是否为平台管理员"""
        return self.role == "admin"

    @property
    def is_anonymous(self) -> bool:
        """是否为匿名用户"""
        return self.anonymous_user_id is not None

    @property
    def has_identity(self) -> bool:
        """是否有有效身份"""
        return self.user_id is not None or self.anonymous_user_id is not None

    @property
    def has_team(self) -> bool:
        """是否已附加团队上下文"""
        return self.team_id is not None

    @property
    def is_team_admin(self) -> bool:
        """是否为团队管理员或所有者（不含平台 admin）"""
        return self.team_role in {"owner", "admin"}

    @property
    def is_team_owner(self) -> bool:
        """是否为团队所有者"""
        return self.team_role == "owner"

    def with_team(
        self,
        team_id: uuid.UUID,
        team_role: str,
    ) -> "PermissionContext":
        """返回附加了团队上下文的新实例（不可变）"""
        return PermissionContext(
            user_id=self.user_id,
            anonymous_user_id=self.anonymous_user_id,
            role=self.role,
            team_id=team_id,
            team_role=team_role,
        )


# 使用 ContextVar 在请求生命周期内传递权限上下文
_permission_context: ContextVar[PermissionContext | None] = ContextVar(
    "permission_context", default=None
)


def get_permission_context() -> PermissionContext | None:
    """获取当前权限上下文"""
    return _permission_context.get()


def set_permission_context(ctx: PermissionContext | None) -> None:
    """设置当前权限上下文"""
    _permission_context.set(ctx)


def clear_permission_context() -> None:
    """清除当前权限上下文"""
    _permission_context.set(None)


__all__ = [
    "PermissionContext",
    "clear_permission_context",
    "get_permission_context",
    "set_permission_context",
]
