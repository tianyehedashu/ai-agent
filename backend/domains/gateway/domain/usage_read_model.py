"""Gateway 管理读模型：用量在日志/大盘上的聚合维度。

本模块与以下概念**正交**，禁止混用命名：

- **Tenancy** ``Team.kind``（``personal`` / ``shared``）：团队实体分型；personal team 仍是 ``Team`` 表的一行。
- **预算** ``BudgetScope``（``system`` / ``team`` / ``key`` / ``user``）：预算作用域类型。

``UsageAggregation`` **仅**用于管理面 ``GET /logs``、``GET /logs/{id}``、``GET /dashboard/summary`` 的查询切片：

- ``workspace``：按当前 ``ManagementTeamContext.team_id``（由 ``X-Team-Id`` 解析）过滤/聚合；该 ID 可为 **personal** 或 **shared** 工作区。
- ``user``：按当前 JWT 对应 ``user_id`` 跨工作区聚合/过滤；**不**表示「无团队用户」。
"""

from __future__ import annotations

from enum import StrEnum


class UsageAggregation(StrEnum):
    """管理面请求日志 / 大盘读模型切片。"""

    WORKSPACE = "workspace"
    USER = "user"


__all__ = ["UsageAggregation"]
