"""
Gateway Management Router (/api/v1/gateway/*)

聚合入口 — 按现有 section 注释拆分至 ``presentation/routers/`` 子模块,本文件仅 ``include_router``：

- ``team_scoped``   : ``/teams/{team_id}/*`` 团队资源（keys / credentials / models / …）
- ``my_credentials``: ``/my-credentials`` 用户私有凭据（JWT only, 不要求 team 路径）
- ``my_models``     : ``/my-models`` 个人注册模型 + ``/models/available``（用户域）

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
    credential_copy,
    managed_team_credentials,
    managed_team_models,
    managed_team_routes,
    managed_team_virtual_keys,
    model_copy,
    my_credentials,
    my_models,
    playground,
    provider_profiles,
    system_visibility,
    team_scoped,
)

router = APIRouter(tags=["AI Gateway"])

router.include_router(team_scoped.router)
router.include_router(my_credentials.router)
router.include_router(playground.router)
router.include_router(credential_copy.router)
router.include_router(model_copy.router)
router.include_router(managed_team_credentials.router)
router.include_router(managed_team_models.router)
router.include_router(managed_team_routes.router)
router.include_router(managed_team_virtual_keys.router)
router.include_router(my_models.router)
router.include_router(provider_profiles.router)
router.include_router(system_visibility.router)
router.include_router(system_visibility.admin_router)

__all__ = ["router"]
