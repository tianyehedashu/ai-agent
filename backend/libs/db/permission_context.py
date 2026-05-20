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
        team_id: 当前 **活动团队租户**（X-Team-Id 解析结果）
        team_role: 当前团队角色（owner/admin/member），仅 team_id 非空时有意义
        team_ids: 用户可访问的全部 tenant_id（经 team_members）；admin 时为空集表示不过滤
    """

    user_id: uuid.UUID | None = None
    anonymous_user_id: str | None = None
    role: str = "user"
    team_id: uuid.UUID | None = None
    team_role: str | None = None
    team_ids: frozenset[uuid.UUID] = frozenset()

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
            team_ids=self.team_ids,
        )

    def with_team_ids(self, team_ids: frozenset[uuid.UUID]) -> "PermissionContext":
        """返回附加了可访问租户集合的新实例。"""
        return PermissionContext(
            user_id=self.user_id,
            anonymous_user_id=self.anonymous_user_id,
            role=self.role,
            team_id=self.team_id,
            team_role=self.team_role,
            team_ids=team_ids,
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


def merge_team_into_permission_context(
    *,
    team_id: uuid.UUID,
    team_role: str,
) -> None:
    """在已有 PermissionContext 上附加活动团队，保留 ``team_ids``。"""
    existing = get_permission_context()
    if existing is None:
        msg = "PermissionContext must be set before merge_team_into_permission_context"
        raise RuntimeError(msg)
    set_permission_context(existing.with_team(team_id, team_role))


def ensure_tenant_in_team_ids(
    team_ids: frozenset[uuid.UUID],
    tenant_id: uuid.UUID,
) -> frozenset[uuid.UUID]:
    """确保活动租户在可访问集合内（Gateway /v1 等无 JWT 入口兜底）。"""
    if tenant_id in team_ids:
        return team_ids
    return team_ids | frozenset({tenant_id})


__all__ = [
    "PermissionContext",
    "clear_permission_context",
    "ensure_tenant_in_team_ids",
    "get_permission_context",
    "merge_team_into_permission_context",
    "set_permission_context",
]
