"""``UsageAxis`` - 仓储层日志查询/聚合的过滤维度（值对象）。

与 ``domains.gateway.domain.usage_read_model.UsageAggregation`` 的关系：

- ``UsageAggregation``（产品视角枚举，``workspace`` / ``user``）：路由层接收的 HTTP 查询参数。
- ``UsageAxis``（仓储层值对象，``workspace`` 轴 / ``user`` 轴）：把"二选一切片"具象化为
  SQL WHERE 子句模板，让 ``RequestLogRepository`` 的 ``list / get / aggregate_*`` 共享单份实现。

`UsageAxis.workspace` 轴对应 ``WHERE team_id = X`` 加可选 *member-only* 子约束（团队普通成员
仅可见自己创建的非系统 vkey 行 + 自己 user_id 的平台入站行）；``UsageAxis.user`` 轴对应
``WHERE user_id = Y``。

与 ``BudgetScope`` / ``CredentialScope`` 正交（后两者是写入归属层级，不参与本值对象的语义）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from sqlalchemy import and_, exists, or_, select

from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.sql import ColumnElement


UsageAxisKind = Literal["workspace", "user"]
"""``UsageAxis.kind`` 的合法字面量；与 ``UsageAggregation`` 同字面量但语义独立
（前者是仓储层值对象，后者是路由层产品视角枚举）。"""


@dataclass(frozen=True)
class UsageAxis:
    """日志查询/聚合的过滤维度。

    构造经 ``UsageAxis.workspace`` / ``UsageAxis.user`` 工厂；
    SQL 子句经 ``base_clauses()`` 生成，仓储层方法只负责拼装其它维度（时间窗、状态、
    capability、vkey_id、credential_id 等）。

    - ``workspace`` 轴：``team_id`` 必填，``user_id`` 必为 None；可选 ``member_user_id``
      附加"团队普通成员仅可见自己的非系统 vkey 行 + 自己的平台入站行"约束。
    - ``user`` 轴：``user_id`` 必填，其它字段必为 None。
    """

    kind: UsageAxisKind
    team_id: UUID | None = None
    user_id: UUID | None = None
    member_user_id: UUID | None = None

    @classmethod
    def workspace(
        cls,
        team_id: UUID,
        *,
        member_user_id: UUID | None = None,
    ) -> UsageAxis:
        """按团队过滤；可选 ``member_user_id`` 表达"团队普通成员"可见性约束。"""
        return cls(
            kind="workspace",
            team_id=team_id,
            member_user_id=member_user_id,
        )

    @classmethod
    def user(cls, user_id: UUID) -> UsageAxis:
        """按当前账号跨团队过滤。"""
        return cls(kind="user", user_id=user_id)

    def is_workspace(self) -> bool:
        return self.kind == "workspace"

    def is_user(self) -> bool:
        return self.kind == "user"

    def base_clauses(self) -> list[ColumnElement[bool]]:
        """生成基础 WHERE 子句（不含其它维度的过滤）。

        - workspace 轴：``team_id = X``；当配置 ``member_user_id`` 时附加可见性约束
          （本人非系统 vkey 行 OR 本人 user_id 的平台入站行）。
        - user 轴：``user_id = Y``。

        不变量由两个工厂保证；若直接以非法 ``kind`` 构造（绕过工厂）则在此显式抛错，
        Python ``-O`` 模式仍能正确 fail（不依赖 ``assert``）。
        """
        if self.kind == "workspace":
            if self.team_id is None:
                raise ValueError("UsageAxis.workspace requires team_id")
            clauses: list[ColumnElement[bool]] = [GatewayRequestLog.team_id == self.team_id]
            if self.member_user_id is not None:
                member_own_vkey = exists(
                    select(1)
                    .select_from(GatewayVirtualKey)
                    .where(
                        GatewayVirtualKey.id == GatewayRequestLog.vkey_id,
                        GatewayVirtualKey.team_id == self.team_id,
                        GatewayVirtualKey.created_by_user_id == self.member_user_id,
                        GatewayVirtualKey.is_system.is_(False),
                    )
                )
                own_platform_inbound = and_(
                    GatewayRequestLog.vkey_id.is_(None),
                    GatewayRequestLog.user_id == self.member_user_id,
                )
                clauses.append(or_(member_own_vkey, own_platform_inbound))
            return clauses

        if self.kind == "user":
            if self.user_id is None:
                raise ValueError("UsageAxis.user requires user_id")
            return [GatewayRequestLog.user_id == self.user_id]

        raise ValueError(f"Unknown UsageAxis.kind: {self.kind!r}")


__all__ = ["UsageAxis", "UsageAxisKind"]
