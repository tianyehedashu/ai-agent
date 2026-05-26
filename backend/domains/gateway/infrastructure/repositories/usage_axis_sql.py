"""UsageAxis → SQLAlchemy WHERE 子句（基础设施层）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_, exists, or_, select

from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey

if TYPE_CHECKING:
    from sqlalchemy.sql import ColumnElement


def usage_axis_base_clauses(axis: UsageAxis) -> list[ColumnElement[bool]]:
    """生成基础 WHERE 子句（不含时间窗等其它维度）。

    workspace 轴 ``member_user_id`` 子约束（EXISTS 自有非系统 vkey / 本人 platform 入站）
    须与 ``domains.gateway.domain.policies.usage_log_visibility.member_can_view_request_log_record``
    保持同步。

    user 轴：跨团队按登录用户；含 ``user_id`` 列或本人非系统 vkey 归因（与 workspace member 语义对齐）。
    """
    if axis.kind == "workspace":
        if axis.team_id is None:
            raise ValueError("UsageAxis.workspace requires team_id")
        clauses: list[ColumnElement[bool]] = [GatewayRequestLog.tenant_id == axis.team_id]
        if axis.member_user_id is not None:
            member_own_vkey = exists(
                select(1)
                .select_from(GatewayVirtualKey)
                .where(
                    GatewayVirtualKey.id == GatewayRequestLog.vkey_id,
                    GatewayVirtualKey.tenant_id == axis.team_id,
                    GatewayVirtualKey.created_by_user_id == axis.member_user_id,
                    GatewayVirtualKey.is_system.is_(False),
                )
            )
            own_platform_inbound = and_(
                GatewayRequestLog.vkey_id.is_(None),
                GatewayRequestLog.user_id == axis.member_user_id,
            )
            clauses.append(or_(member_own_vkey, own_platform_inbound))
        return clauses

    if axis.kind == "user":
        if axis.user_id is None:
            raise ValueError("UsageAxis.user requires user_id")
        # 跨团队「我」：user_id 列命中，或经本人非系统 vkey 归因（Router 回调可能未写 user_id）
        member_own_vkey = exists(
            select(1)
            .select_from(GatewayVirtualKey)
            .where(
                GatewayVirtualKey.id == GatewayRequestLog.vkey_id,
                GatewayVirtualKey.created_by_user_id == axis.user_id,
                GatewayVirtualKey.is_system.is_(False),
            )
        )
        own_platform_inbound = and_(
            GatewayRequestLog.vkey_id.is_(None),
            GatewayRequestLog.user_id == axis.user_id,
        )
        vkey_attributed = and_(
            GatewayRequestLog.vkey_id.isnot(None),
            or_(
                GatewayRequestLog.user_id == axis.user_id,
                member_own_vkey,
            ),
        )
        return [or_(own_platform_inbound, vkey_attributed)]

    raise ValueError(f"Unknown UsageAxis.kind: {axis.kind!r}")


__all__ = ["usage_axis_base_clauses"]
