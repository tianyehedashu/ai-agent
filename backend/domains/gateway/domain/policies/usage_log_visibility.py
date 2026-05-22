"""网关请求日志：团队 member 可见性策略（纯函数）。

列表侧 SQL（``usage_axis_sql``）的 member 子约束须与
``member_can_view_request_log_record`` 语义保持一致。
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID  # noqa: TC003

from domains.tenancy.domain.policies.team_role import is_plain_team_member_role


@dataclass(frozen=True)
class UsageLogAccessSnapshot:
    """管理面读侧所需的团队/角色快照。"""

    is_platform_admin: bool
    team_role: str
    user_id: UUID
    team_id: UUID


def snapshot_is_team_member_only(snapshot: UsageLogAccessSnapshot) -> bool:
    """与 ``tenancy.is_team_member_only`` 规则一致（基于快照，无 IO）。"""
    return is_plain_team_member_role(
        is_platform_admin=snapshot.is_platform_admin,
        team_role=snapshot.team_role,
    )


def workspace_axis_member_user_id(
    snapshot: UsageLogAccessSnapshot,
    *,
    vkey_id: UUID | None = None,
) -> UUID | None:
    """WORKSPACE 聚合轴是否附加 member 子约束（仅可见本人相关行）。

    ``vkey_id`` 由仓储 ``list_by_axis`` 作额外 WHERE；policy 不因筛选取消子约束。
    成员按他人 vkey 筛选时 SQL 自然返回空集（与单条详情 403 一致）。
    """
    _ = vkey_id
    if snapshot.is_platform_admin:
        return None
    if snapshot_is_team_member_only(snapshot):
        return snapshot.user_id
    return None


def member_requires_request_log_detail_filter(snapshot: UsageLogAccessSnapshot) -> bool:
    """单条日志详情是否需 member 级可见性过滤。"""
    return snapshot_is_team_member_only(snapshot)


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
    "snapshot_is_team_member_only",
    "usage_log_access_from_management_ctx",
    "workspace_axis_member_user_id",
]
