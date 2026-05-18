"""
Gateway Management Router (/api/v1/gateway/*)

聚合入口 — 按现有 section 注释拆分至 ``presentation/routers/`` 子模块,本文件仅 ``include_router``：

- ``virtual_keys``  : ``/keys`` 列表 / 创建 / 撤销
- ``credentials``   : ``/credentials`` 团队凭据 CRUD + 探测 + 批量导入
- ``my_credentials``: ``/my-credentials`` 用户私有凭据（JWT only,不要求 X-Team-Id）
- ``my_models``     : ``/my-models`` 个人注册模型 + ``/models/available``
- ``models``        : ``/models`` 团队模型 + ``/models/presets`` + ``/admin/credential-stats``
- ``routes``        : ``/routes`` 虚拟路由
- ``budgets``       : ``/budgets`` 预算
- ``logs``          : ``/logs`` 调用日志（``UsageAggregation`` workspace/user 切片）
- ``dashboard``     : ``/dashboard/summary``、``/dashboard/margin``
- ``alerts``        : ``/alerts/rules``、``/alerts/events``
- ``plans``         : ``ProviderPlan`` + ``EntitlementPlan``

团队 CRUD 与成员见 ``domains.tenancy.presentation.teams_router``（同前缀挂载）。

RBAC 矩阵见 plan：
- 平台 admin：全部
- team owner：自团队全部
- team admin：成员管理外的写操作
- team member：自己创建的资源 + 只读
"""

from __future__ import annotations

from fastapi import APIRouter

from domains.gateway.presentation.routers import (
    alerts,
    budgets,
    credentials,
    dashboard,
    logs,
    models,
    my_credentials,
    my_models,
    plans,
    routes,
    virtual_keys,
)

router = APIRouter(prefix="/api/v1/gateway", tags=["AI Gateway"])

router.include_router(virtual_keys.router)
router.include_router(credentials.router)
router.include_router(my_credentials.router)
router.include_router(my_models.router)
router.include_router(models.router)
router.include_router(routes.router)
router.include_router(budgets.router)
router.include_router(logs.router)
router.include_router(dashboard.router)
router.include_router(alerts.router)
router.include_router(plans.router)

__all__ = ["router"]
