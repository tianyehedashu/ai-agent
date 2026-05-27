"""Gateway 管理读模型：用量在日志/大盘上的聚合维度。

本模块与以下概念**正交**，禁止混用命名：

- **Tenancy** ``Team.kind``（``personal`` / ``shared``）：团队实体分型；personal team
  仍是 ``Team`` 表的一行。前端 ``GatewayScopeTab`` 取值与之对齐（``personal | shared``）。
- **预算** ``BudgetScope``（``system`` / ``team`` / ``key`` / ``user``）：预算作用域类型。
- **凭据** ``CredentialScope``（``system`` / ``team`` / ``user``）：上游凭据归属层级。

``UsageAggregation`` **仅**用于管理面 ``GET /logs``、``GET /logs/{id}``、
``GET /dashboard/summary`` 的查询切片：

- ``workspace``（产品文案：**团队**）：按当前 ``ManagementTeamContext.team_id``
  （由 URL ``/teams/{team_id}`` 或 legacy ``X-Team-Id`` 解析）过滤/聚合；该 ID 可为 **personal** 或 **shared** 团队。
- ``user``（产品文案：**我**）：按当前 JWT 对应 ``user_id`` 跨团队聚合/过滤；
  **不**表示「无团队用户」。

字面量保留 ``workspace`` 而不与 ``BudgetScope.team`` 共用 ``team``，是为了在 URL/JSON 上下文
保证两组枚举可独立解析（详见 ``domains.gateway.domain.types.BudgetScope`` docstring）。

仓储层（Stage 2 起）按 ``UsageAxis`` 值对象统一访问 ``gateway_request_logs``，本枚举仅是
路由/应用层接收的"产品视角"。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID


class UsageAggregation(StrEnum):
    """管理面请求日志 / 大盘读模型切片。"""

    WORKSPACE = "workspace"
    USER = "user"


class UsageStatisticsGroupBy(StrEnum):
    """调用统计支持的分组维度。"""

    CREDENTIAL = "credential"
    USER = "user"
    TEAM = "team"
    MODEL = "model"
    VKEY = "vkey"
    PROVIDER = "provider"
    CAPABILITY = "capability"
    STATUS = "status"


class UsageStatisticsBreakdownBy(StrEnum):
    """行内 breakdown 二次分组（仅凭据 / 模型）。"""

    CREDENTIAL = "credential"
    MODEL = "model"


@dataclass(frozen=True)
class UsageStatisticsFilters:
    """调用统计的可组合过滤条件（纯值对象）。"""

    credential_id: UUID | None = None
    user_id: UUID | None = None
    team_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    capability: str | None = None
    status: str | None = None
    vkey_id: UUID | None = None


@dataclass(frozen=True)
class UsageStatisticsParentScope:
    """行内 breakdown：限定到父维度某一分组键下的日志子集。"""

    group_by: UsageStatisticsGroupBy
    group_key: str


USAGE_AGGREGATION_QUERY_DESCRIPTION = (
    "用量切片：workspace（产品文案：团队）=按当前团队工作区"
    "（URL /teams/{team_id} 或 legacy X-Team-Id；含 personal/shared）;"
    "user（产品文案：我）=按当前登录账号跨团队聚合。"
)
"""``UsageAggregation`` 在 FastAPI ``Query(description=...)`` 中的统一文案；
路由层（``logs.py`` / ``dashboard.py`` 等）共享同一字符串，避免三处漂移。"""


__all__ = [
    "USAGE_AGGREGATION_QUERY_DESCRIPTION",
    "UsageAggregation",
    "UsageStatisticsBreakdownBy",
    "UsageStatisticsFilters",
    "UsageStatisticsGroupBy",
    "UsageStatisticsParentScope",
]
