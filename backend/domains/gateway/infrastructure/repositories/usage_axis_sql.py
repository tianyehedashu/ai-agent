"""UsageAxis → SQLAlchemy WHERE 子句（基础设施层）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Select, and_, or_, select

from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.sql import ColumnElement


def _own_non_system_vkey_ids_subquery(
    *,
    user_id: UUID,
    tenant_id: UUID | None = None,
) -> Select[tuple[UUID]]:
    """本人创建的非系统 vkey id 集合（非 correlated；供 IN / Hash Join）。"""
    clauses = [
        GatewayVirtualKey.created_by_user_id == user_id,
        GatewayVirtualKey.is_system.is_(False),
    ]
    if tenant_id is not None:
        clauses.append(GatewayVirtualKey.tenant_id == tenant_id)
    return select(GatewayVirtualKey.id).where(*clauses)


def usage_axis_user_visibility_disjuncts(
    user_id: UUID,
) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    """user 轴可见性：两段互斥子条件（vkey_id IS NULL vs IS NOT NULL）。"""
    own_vkeys = _own_non_system_vkey_ids_subquery(user_id=user_id)
    platform_inbound = and_(
        GatewayRequestLog.vkey_id.is_(None),
        GatewayRequestLog.user_id == user_id,
    )
    vkey_attributed = and_(
        GatewayRequestLog.vkey_id.isnot(None),
        or_(
            GatewayRequestLog.user_id == user_id,
            GatewayRequestLog.vkey_id.in_(own_vkeys),
        ),
    )
    return platform_inbound, vkey_attributed


def usage_axis_workspace_member_visibility_disjuncts(
    team_id: UUID,
    member_user_id: UUID,
) -> tuple[ColumnElement[bool], ColumnElement[bool]]:
    """workspace member 子约束：两段互斥子条件。"""
    own_vkeys = _own_non_system_vkey_ids_subquery(
        user_id=member_user_id,
        tenant_id=team_id,
    )
    platform_inbound = and_(
        GatewayRequestLog.vkey_id.is_(None),
        GatewayRequestLog.user_id == member_user_id,
    )
    vkey_owned = and_(
        GatewayRequestLog.vkey_id.isnot(None),
        GatewayRequestLog.vkey_id.in_(own_vkeys),
    )
    return platform_inbound, vkey_owned


def usage_axis_count_disjuncts(
    axis: UsageAxis,
) -> tuple[tuple[ColumnElement[bool], ColumnElement[bool]], int] | None:
    """返回可拆分 COUNT 的互斥子条件及其在 ``usage_axis_base_clauses`` 结果中的下标。"""
    if axis.kind == "user":
        if axis.user_id is None:
            raise ValueError("UsageAxis.user requires user_id")
        return usage_axis_user_visibility_disjuncts(axis.user_id), 0
    if axis.kind == "workspace" and axis.member_user_id is not None:
        if axis.team_id is None:
            raise ValueError("UsageAxis.workspace requires team_id")
        return (
            usage_axis_workspace_member_visibility_disjuncts(
                axis.team_id,
                axis.member_user_id,
            ),
            1,
        )
    return None


def usage_axis_base_clauses(axis: UsageAxis) -> list[ColumnElement[bool]]:
    """生成基础 WHERE 子句（不含时间窗等其它维度）。

    workspace 轴 ``member_user_id`` 子约束（自有非系统 vkey / 本人 platform 入站）
    须与 ``domains.gateway.domain.policies.usage_log_visibility.member_can_view_request_log_record``
    保持同步。

    user 轴：跨团队按登录用户；含 ``user_id`` 列或本人非系统 vkey 归因（与 workspace member 语义对齐）。

    platform 轴：无基础约束，覆盖全平台所有请求日志（仅平台管理员；门控在应用层）。
    """
    if axis.kind == "platform":
        return []

    if axis.kind == "workspace":
        if axis.team_id is None:
            raise ValueError("UsageAxis.workspace requires team_id")
        clauses: list[ColumnElement[bool]] = [GatewayRequestLog.tenant_id == axis.team_id]
        if axis.member_user_id is not None:
            platform_inbound, vkey_owned = usage_axis_workspace_member_visibility_disjuncts(
                axis.team_id,
                axis.member_user_id,
            )
            clauses.append(or_(platform_inbound, vkey_owned))
        return clauses

    if axis.kind == "user":
        if axis.user_id is None:
            raise ValueError("UsageAxis.user requires user_id")
        platform_inbound, vkey_attributed = usage_axis_user_visibility_disjuncts(axis.user_id)
        return [or_(platform_inbound, vkey_attributed)]

    raise ValueError(f"Unknown UsageAxis.kind: {axis.kind!r}")


__all__ = [
    "usage_axis_base_clauses",
    "usage_axis_count_disjuncts",
    "usage_axis_user_visibility_disjuncts",
    "usage_axis_workspace_member_visibility_disjuncts",
]
