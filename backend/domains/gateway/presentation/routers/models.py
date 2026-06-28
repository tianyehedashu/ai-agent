"""Team-scope Models 子 router (含 /models/presets, /catalog/reload, /admin/credential-stats)。"""

from __future__ import annotations

from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.gateway.application.catalog.config_catalog_sync import (
    MANAGED_BY_KEY,
    MANAGED_CONFIG,
    model_types_for_gateway_registration,
    selector_capabilities_from_tags,
)
from domains.gateway.application.catalog.gateway_catalog_maintenance import (
    log_gateway_catalog_maintenance_report,
    run_gateway_catalog_maintenance,
)
from domains.gateway.application.catalog.management.model_writes import (
    merge_display_name_into_tags,
)
from domains.gateway.domain.catalog.model_registry_scope import RegistryScope
from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row
from domains.gateway.presentation.deps import (
    CurrentTeam,
)
from domains.gateway.presentation.model_list_query import ModelListQueryDep
from domains.gateway.presentation.schemas.common import (
    GatewayModelBatchDeleteFailureItem,
    GatewayModelBatchDeleteRequest,
    GatewayModelBatchDeleteResponse,
    GatewayModelBatchResyncCapabilitiesRequest,
    GatewayModelBatchResyncCapabilitiesResponse,
    GatewayModelCreate,
    GatewayModelIdsResponse,
    GatewayModelListResponse,
    GatewayModelPresetResponse,
    GatewayModelResponse,
    GatewayModelRouteUsageItem,
    GatewayModelTestResponse,
    GatewayModelUpdate,
    GatewayModelUsageSummaryResponse,
    MultiCredentialGatewayModelCreate,
    MultiCredentialGatewayModelResponse,
    PlatformCredentialStatItem,
    PlatformCredentialStatListResponse,
)
from domains.gateway.presentation.schemas.gateway_model_list_response import (
    build_gateway_model_list_response,
)
from domains.gateway.presentation.schemas.gateway_model_response import build_gateway_model_response
from domains.gateway.presentation.schemas.gateway_usage_list_response import (
    build_gateway_model_usage_summary_response,
    build_platform_credential_stat_list_response,
)
from domains.identity.presentation.deps import AdminUser
from libs.api.pagination import PageParams, page_query_params
from libs.db.database import get_db
from libs.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from libs.rate_limit import check_probe_rate_limit

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()
PageDep = Annotated[PageParams, Depends(page_query_params)]


@router.get("/models/presets", response_model=list[GatewayModelPresetResponse])
async def list_model_presets(
    team: CurrentTeam,
    reads: MgmtReads,
    provider: str | None = Query(None, min_length=1, max_length=50),
) -> list[GatewayModelPresetResponse]:
    """返回已同步到 DB 的配置托管全局模型目录。"""
    _ = team
    system_models = await reads.list_system_gateway_models(only_enabled=True)
    cfg_rows = [m for m in system_models if (m.tags or {}).get(MANAGED_BY_KEY) == MANAGED_CONFIG]
    presets: list[GatewayModelPresetResponse] = [
        GatewayModelPresetResponse(
            id=m.name,
            name=str((m.tags or {}).get("display_name") or m.name),
            provider=m.provider,
            real_model=m.real_model,
            capability=m.capability,
            context_window=int((m.tags or {}).get("context_window") or 0),
            input_price=float((m.tags or {}).get("input_price") or 0.0),
            output_price=float((m.tags or {}).get("output_price") or 0.0),
            supports_vision=bool((m.tags or {}).get("supports_vision", False)),
            supports_tools=bool((m.tags or {}).get("supports_tools", True)),
            supports_reasoning=bool((m.tags or {}).get("supports_reasoning", False)),
            recommended_for=list((m.tags or {}).get("recommended_for") or []),
            description=str((m.tags or {}).get("description") or ""),
            model_types=model_types_for_gateway_registration(m.tags or {}, m.capability),
            selector_capabilities=selector_capabilities_from_tags(
                m.tags or {}, provider=m.provider, real_model=m.real_model
            ),
        )
        for m in cfg_rows
    ]
    if provider is not None:
        presets = [p for p in presets if p.provider == provider]
    return presets


@router.post("/catalog/reload-from-config")
async def reload_gateway_catalog_from_config(
    _: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    writes: MgmtWrites,
) -> dict[str, Any]:
    """平台管理员：从 gateway-catalog.seed.json 重新同步全局模型目录并重载 LiteLLM Router。"""
    report = await run_gateway_catalog_maintenance(db, settings=settings)
    log_gateway_catalog_maintenance_report(report)
    await writes.reload_litellm_router()
    return {"ok": True, **report.to_api_dict()}


@router.get("/models", response_model=GatewayModelListResponse)
async def list_models(
    team: CurrentTeam,
    reads: MgmtReads,
    query: ModelListQueryDep,
    registry_scope: RegistryScope = Query(
        "team",
        description=(
            "team=当前团队注册行（不含 scope=user BYOK）；system=平台注册行（仅平台管理员）；"
            "callable=租户+平台合并；requestable=enabled 且连通性未 failed（试调/请求用）；"
            "system_requestable=成员可见且可请求的系统模型（enabled、未 failed、应用可见性）"
        ),
    ),
) -> GatewayModelListResponse:
    if registry_scope == "system" and not team.is_platform_admin:
        raise PermissionDeniedError(
            message="Only platform admin can list system registry models",
            resource="system registry models",
        )
    page = await reads.list_gateway_models_page(
        team.team_id,
        query,
        registry_scope=registry_scope,
        only_enabled=False,
        user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
    include_cred = registry_scope == "system" and team.is_platform_admin
    credentials_by_id = None
    team_credentials_by_id = None
    if include_cred:
        cred_ids = {
            m.credential_id for m in page.items if registry_kind_for_merged_row(m) == "system"
        }
        credentials_by_id = await reads.map_system_credentials_by_id(cred_ids)
    if registry_scope == "team":
        team_cred_ids = {
            m.credential_id for m in page.items if registry_kind_for_merged_row(m) == "team"
        }
        team_credentials_by_id = await reads.map_team_credentials_display_by_id(
            team_cred_ids,
        )
    return build_gateway_model_list_response(
        page,
        include_system_credential=include_cred,
        credentials_by_id=credentials_by_id if include_cred else None,
        team_credentials_by_id=team_credentials_by_id,
    )


@router.get("/models/ids", response_model=GatewayModelIdsResponse)
async def list_model_ids(
    team: CurrentTeam,
    reads: MgmtReads,
    query: ModelListQueryDep,
    registry_scope: RegistryScope = Query("team"),
) -> GatewayModelIdsResponse:
    if registry_scope == "system" and not team.is_platform_admin:
        raise PermissionDeniedError(
            message="Only platform admin can list system registry models",
            resource="system registry models",
        )
    result = await reads.list_gateway_model_ids(
        team.team_id,
        query,
        registry_scope=registry_scope,
        only_enabled=False,
        user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
    return GatewayModelIdsResponse(ids=result.ids, truncated=result.truncated)


@router.get("/models/usage-summary", response_model=GatewayModelUsageSummaryResponse)
async def models_usage_summary(
    team: CurrentTeam,
    reads: MgmtReads,
    page: PageDep,
    days: int = Query(7, ge=1, le=90),
    provider: str | None = Query(None, min_length=1, max_length=50),
    route_names: list[str] | None = Query(
        default=None,
        description=(
            "仅聚合指定 route（与注册模型 name 对齐）。"
            "传入时忽略 page/page_size，仅返回匹配 route 的用量。"
        ),
    ),
) -> GatewayModelUsageSummaryResponse:
    """按当前团队注册模型名与请求日志 ``route_name`` 对齐；见 ``UsageAggregation`` 文档。"""
    if route_names is not None and len(route_names) > 200:
        route_names = route_names[:200]
    items, total, start, end = await reads.aggregate_gateway_model_route_usage(
        team,
        days=days,
        provider=provider,
        route_names=route_names,
        page=page.page,
        page_size=page.page_size,
    )
    validated_items = [GatewayModelRouteUsageItem.model_validate(i) for i in items]
    return build_gateway_model_usage_summary_response(
        items=validated_items,
        total=total,
        page=page.page,
        page_size=page.page_size,
        start=start,
        end=end,
    )


@router.get("/models/{model_id}", response_model=GatewayModelResponse)
async def get_model(
    model_id: uuid.UUID,
    team: CurrentTeam,
    reads: MgmtReads,
    registry_scope: RegistryScope = Query("team"),
) -> GatewayModelResponse:
    row = await reads.get_gateway_registry_model(
        model_id,
        team.team_id,
        is_platform_admin=team.is_platform_admin,
    )
    if row is None:
        raise NotFoundError("Model")
    include_cred = registry_scope == "system" and team.is_platform_admin
    credentials_by_id = None
    team_credentials_by_id = None
    if include_cred and registry_kind_for_merged_row(row) == "system":
        credentials_by_id = await reads.map_system_credentials_by_id({row.credential_id})
    if registry_kind_for_merged_row(row) == "team":
        team_credentials_by_id = await reads.map_team_credentials_display_by_id(
            {row.credential_id},
        )
    return build_gateway_model_response(
        row,
        include_system_credential=include_cred,
        credentials_by_id=credentials_by_id,
        team_credentials_by_id=team_credentials_by_id,
    )


@router.get("/admin/credential-stats", response_model=PlatformCredentialStatListResponse)
async def admin_credential_stats(
    team: CurrentTeam,
    reads: MgmtReads,
    page: PageDep,
    days: int = Query(7, ge=1, le=90),
) -> PlatformCredentialStatListResponse:
    if not team.is_platform_admin:
        raise PermissionDeniedError(
            message="Only platform admin can view credential stats",
            resource="credential stats",
        )
    rows, total = await reads.list_platform_credential_stats(
        days=days,
        page=page.page,
        page_size=page.page_size,
    )
    stat_items = [PlatformCredentialStatItem.model_validate(r) for r in rows]
    return build_platform_credential_stat_list_response(
        items=stat_items,
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.post("/models", response_model=GatewayModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: GatewayModelCreate,
    team: CurrentTeam,
    reads: MgmtReads,
    writes: MgmtWrites,
) -> GatewayModelResponse:
    cred = await reads.get_managed_credential_for_team(
        body.credential_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
    # 若注册别名已存在且凭据不同，自动转化为多凭据路由（追加到已有 Route 或新建 Route）
    effective_tags = merge_display_name_into_tags(body.tags, body.display_name)
    existing = await reads._models.get_by_name(team.team_id, body.name)
    if existing is not None:
        if str(existing.credential_id) == str(body.credential_id):
            raise ConflictError(
                message=f"模型名称 '{body.name}' 在该团队中已存在且绑定了相同凭据，请勿重复添加",
                resource="gateway model",
            )
        model = await writes.append_credential_to_existing_model_name(
            tenant_id=team.team_id,
            name=body.name,
            capability=body.capability,
            real_model=body.real_model,
            credential_id=body.credential_id,
            provider=body.provider,
            weight=body.weight,
            rpm_limit=body.rpm_limit,
            tpm_limit=body.tpm_limit,
            tags=effective_tags,
            upstream_call_shape=body.upstream_call_shape,
            actor_user_id=team.user_id,
            team_role=team.team_role,
            is_platform_admin=team.is_platform_admin,
            enabled=body.enabled,
        )
    else:
        model = await writes.create_managed_gateway_model(
            credential_scope=cred.scope,
            tenant_id=team.team_id,
            name=body.name,
            capability=body.capability,
            real_model=body.real_model,
            credential_id=body.credential_id,
            provider=body.provider,
            weight=body.weight,
            rpm_limit=body.rpm_limit,
            tpm_limit=body.tpm_limit,
            tags=effective_tags,
            upstream_call_shape=body.upstream_call_shape,
            actor_user_id=team.user_id,
            team_role=team.team_role,
            is_platform_admin=team.is_platform_admin,
            enabled=body.enabled,
        )
    team_credentials_by_id = await reads.map_team_credentials_display_by_id(
        {model.credential_id},
    )
    return build_gateway_model_response(
        model,
        team_credentials_by_id=team_credentials_by_id,
    )


@router.post(
    "/models/multi-credential",
    response_model=MultiCredentialGatewayModelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_multi_credential_model(
    body: MultiCredentialGatewayModelCreate,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> MultiCredentialGatewayModelResponse:
    """同 ``(provider, real_model)`` 多凭据一键注册 + 自动 ``GatewayRoute``，启用 Router 负载均衡。"""
    result = await writes.create_multi_credential_gateway_model(
        tenant_id=team.team_id,
        name=body.name,
        capability=body.capability,
        real_model=body.real_model,
        provider=body.provider,
        credential_ids=list(body.credential_ids),
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
        strategy=body.strategy.value,
        weight=body.weight,
        rpm_limit=body.rpm_limit,
        tpm_limit=body.tpm_limit,
        tags=body.tags,
        upstream_call_shape=body.upstream_call_shape,
        enabled=body.enabled,
    )
    route = result.route
    models = result.models
    return MultiCredentialGatewayModelResponse(
        route_id=route.id,
        virtual_model=route.virtual_model,
        strategy=route.strategy,
        primary_models=list(route.primary_models or []),
        created_model_ids=[m.id for m in models],
    )


@router.patch("/models/{model_id}", response_model=GatewayModelResponse)
async def update_model(
    model_id: uuid.UUID,
    body: GatewayModelUpdate,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> GatewayModelResponse:
    updated = await writes.update_gateway_model(
        model_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
        fields=body.model_dump(exclude_unset=True, exclude_none=True),
    )
    return build_gateway_model_response(updated)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> None:
    await writes.delete_gateway_model(
        model_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )


@router.post("/models/batch-delete", response_model=GatewayModelBatchDeleteResponse)
async def batch_delete_models(
    payload: GatewayModelBatchDeleteRequest,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> GatewayModelBatchDeleteResponse:
    result = await writes.delete_gateway_models_batch(
        payload.model_ids,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
    return GatewayModelBatchDeleteResponse(
        succeeded=result.succeeded,
        failed=[
            GatewayModelBatchDeleteFailureItem(
                id=item.id,
                code=item.code,
                message=item.message,
            )
            for item in result.failed
        ],
        grants_removed=result.grants_removed,
        budgets_removed=result.budgets_removed,
    )


@router.post(
    "/models/batch-resync-capabilities",
    response_model=GatewayModelBatchResyncCapabilitiesResponse,
)
async def batch_resync_model_capabilities(
    payload: GatewayModelBatchResyncCapabilitiesRequest,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> GatewayModelBatchResyncCapabilitiesResponse:
    result = await writes.resync_gateway_models_capabilities_batch(
        payload.model_ids,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
    return GatewayModelBatchResyncCapabilitiesResponse(
        succeeded=result.succeeded,
        failed=[
            GatewayModelBatchDeleteFailureItem(
                id=item.id,
                code=item.code,
                message=item.message,
            )
            for item in result.failed
        ],
    )


@router.post("/models/{model_id}/test", response_model=GatewayModelTestResponse)
async def test_model(
    model_id: uuid.UUID,
    team: CurrentTeam,
    writes: MgmtWrites,
) -> GatewayModelTestResponse:
    """对 Gateway 团队模型发起一次最小调用做连通性测试（chat / embedding / 生图 / 视频生成）。

    成功/失败均返回 200 + ``success`` 字段，结果同步落库（``last_test_status``
    / ``last_tested_at``），列表页可直接通过 invalidate ``GET /models`` 刷新。

    频率限制：同一用户同一模型每分钟只允许 1 次测试。
    """
    await check_probe_rate_limit(team.user_id, model_id)
    result = await writes.test_gateway_model(
        model_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        team_role=team.team_role,
        is_platform_admin=team.is_platform_admin,
    )
    return GatewayModelTestResponse.model_validate(result)


__all__ = ["router"]
