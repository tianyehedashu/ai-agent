"""网关请求日志：团队 member 可见性策略（纯函数）。"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class UsageLogAccessSnapshot:
    """管理面读侧所需的团队/角色快照。"""

    is_platform_admin: bool
    team_role: str
    user_id: UUID
    team_id: UUID


def workspace_axis_member_user_id(
    snapshot: UsageLogAccessSnapshot,
    *,
    vkey_id: UUID | None,
) -> UUID | None:
    """WORKSPACE 聚合轴是否附加 member 子约束（仅可见本人相关行）。"""
    if snapshot.is_platform_admin:
        return None
    if snapshot.team_role == "member" and vkey_id is None:
        return snapshot.user_id
    return None


def member_requires_request_log_detail_filter(snapshot: UsageLogAccessSnapshot) -> bool:
    """单条日志详情是否需 member 级可见性过滤。"""
    return not snapshot.is_platform_admin and snapshot.team_role == "member"


def member_can_view_request_log_record(
    snapshot: UsageLogAccessSnapshot,
    *,
    record_user_id: UUID | None,
    record_has_vkey: bool,
    vkey_owned_by_user: bool,
) -> bool:
    """团队成员是否允许查看该条请求日志。"""
    if not member_requires_request_log_detail_filter(snapshot):
        return True
    if not record_has_vkey:
        return record_user_id == snapshot.user_id
    return vkey_owned_by_user


def usage_log_access_from_management_ctx(ctx: object) -> UsageLogAccessSnapshot:
    """从 ``ManagementTeamContext`` 构造快照（避免 policy 依赖 infrastructure）。"""
    return UsageLogAccessSnapshot(
        is_platform_admin=bool(getattr(ctx, "is_platform_admin", False)),
        team_role=str(getattr(ctx, "team_role", "member")),
        user_id=ctx.user_id,
        team_id=ctx.team_id,
    )


__all__ = [
    "UsageLogAccessSnapshot",
    "member_can_view_request_log_record",
    "member_requires_request_log_detail_filter",
    "usage_log_access_from_management_ctx",
    "workspace_axis_member_user_id",
]
