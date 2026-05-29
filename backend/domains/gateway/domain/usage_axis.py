"""``UsageAxis`` - 日志查询/聚合的过滤维度（纯值对象，无 SQL）。

与 ``domains.gateway.domain.usage_read_model.UsageAggregation`` 的关系：

- ``UsageAggregation``（产品视角枚举，``workspace`` / ``user`` / ``platform``）：路由层接收的 HTTP 查询参数。
- ``UsageAxis``（仓储层值对象，``workspace`` 轴 / ``user`` 轴 / ``platform`` 轴）：由 infrastructure
  ``usage_axis_sql.usage_axis_base_clauses`` 转为 SQL WHERE。

`UsageAxis.workspace` 轴对应按 ``team_id`` 过滤，可选 member-only 可见性约束；
``UsageAxis.user`` 轴对应 ``user_id`` 过滤；
``UsageAxis.platform`` 轴无基础约束（覆盖全平台），仅平台管理员可解析（门控在应用层）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid

UsageAxisKind = Literal["workspace", "user", "platform"]


@dataclass(frozen=True)
class UsageAxis:
    """日志查询/聚合的过滤维度。

    构造经 ``UsageAxis.workspace`` / ``UsageAxis.user`` / ``UsageAxis.platform`` 工厂；
    SQL 子句在 ``infrastructure.repositories.usage_axis_sql`` 生成。
    """

    kind: UsageAxisKind
    team_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    member_user_id: uuid.UUID | None = None

    @classmethod
    def workspace(
        cls,
        team_id: uuid.UUID,
        *,
        member_user_id: uuid.UUID | None = None,
    ) -> UsageAxis:
        return cls(
            kind="workspace",
            team_id=team_id,
            member_user_id=member_user_id,
        )

    @classmethod
    def user(cls, user_id: uuid.UUID) -> UsageAxis:
        return cls(kind="user", user_id=user_id)

    @classmethod
    def platform(cls) -> UsageAxis:
        """全平台轴（无租户/用户约束，覆盖所有请求日志）。仅平台管理员可用。"""
        return cls(kind="platform")

    def is_workspace(self) -> bool:
        return self.kind == "workspace"

    def is_user(self) -> bool:
        return self.kind == "user"

    def is_platform(self) -> bool:
        return self.kind == "platform"


__all__ = ["UsageAxis", "UsageAxisKind"]
