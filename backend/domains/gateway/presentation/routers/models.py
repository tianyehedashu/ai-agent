"""Team-scope Models 子 router (含 /models/presets, /catalog/reload, /admin/credential-stats)。"""

from __future__ import annotations

from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config_loader import get_app_config
from domains.gateway.application.catalog_capability import infer_catalog_capability
from domains.gateway.application.config_catalog_sync import (
    MANAGED_BY_KEY,
    MANAGED_CONFIG,
    _build_tags_from_model_info,
    model_types_for_gateway_registration,
    selector_capabilities_from_tags,
    sync_app_config_gateway_catalog,
)
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
)
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    GatewayModelCreate,
    GatewayModelPresetResponse,
    GatewayModelResponse,
    GatewayModelTestResponse,
    GatewayModelUpdate,
    GatewayModelUsageSummaryResponse,
    MultiCredentialGatewayModelCreate,
    MultiCredentialGatewayModelResponse,
    PlatformCredentialStatItem,
)
from domains.gateway.presentation.tenant_scoped_response import tenant_scoped_orm_dict
from domains.identity.presentation.deps import AdminUser
from libs.db.database import get_db
from libs.exceptions import HttpMappableDomainError, ValidationError

from ._common import (
    MgmtReads,
    MgmtWrites,
)

router = APIRouter()


@router.get("/models/presets", response_model=list[GatewayModelPresetResponse])
async def list_model_presets(
    team: CurrentTeam,
    reads: MgmtReads,
    provider: str | None = Query(None, min_length=1, max_length=50),
) -> list[GatewayModelPresetResponse]:
    """返回已同步到 DB 的配置托管全局模型目录；若无则回退 app.toml（兼容旧环境）。"""
    _ = team
    system_models = await reads.list_system_gateway_models(only_enabled=True)
    cfg_rows = [
        m
        for m in system_models
        if (m.tags or {}).get(MANAGED_BY_KEY) == MANAGED_CONFIG
    ]
    presets: list[GatewayModelPresetResponse]
    if cfg_rows:
        presets = [
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
                selector_capabilities=selector_capabilities_from_tags(m.tags or {}),
            )
            for m in cfg_rows
        ]
    else:
        presets = []
        for model in get_app_config().models.available:
            if not (model.litellm_model or model.id):
                continue
            tags = _build_tags_from_model_info(model)
            cap = infer_catalog_capability(model)
            presets.append(
                GatewayModelPresetResponse(
                    id=model.id,
                    name=model.name,
                    provider=model.provider,
                    real_model=model.litellm_model or model.id,
                    capability=cap,
                    context_window=model.context_window,
                    input_price=model.input_price,
                    output_price=model.output_price,
                    supports_vision=model.supports_vision,
                    supports_tools=model.supports_tools,
                    supports_reasoning=model.supports_reasoning,
                    recommended_for=list(model.recommended_for),
                    description=model.description,
                    model_types=model_types_for_gateway_registration(tags, cap),
                    selector_capabilities=selector_capabilities_from_tags(tags),
                )
            )
    if provider is not None:
        presets = [p for p in presets if p.provider == provider]
    return presets


@router.post("/catalog/reload-from-config")
async def reload_gateway_catalog_from_config(
    _: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    writes: MgmtWrites,
) -> dict[str, Any]:
    """平台管理员：从 app.toml 重新同步全局模型目录并重载 LiteLLM Router。"""
    stats = await sync_app_config_gateway_catalog(db)
    await db.commit()
    await writes.reload_litellm_router()
    return {"ok": True, **stats}


@router.get("/models", response_model=list[GatewayModelResponse])
async def list_models(
    team: CurrentTeam,
    reads: MgmtReads,
    provider: str | None = Query(None, min_length=1, max_length=50),
    credential_id: uuid.UUID | None = Query(None),
) -> list[GatewayModelResponse]:
    models = await reads.list_gateway_models(
        team.team_id,
        only_enabled=False,
        provider=provider,
        credential_id=credential_id,
    )
    return [GatewayModelResponse.model_validate(tenant_scoped_orm_dict(m)) for m in models]


@router.get("/models/usage-summary", response_model=GatewayModelUsageSummaryResponse)
async def models_usage_summary(
    team: CurrentTeam,
    reads: MgmtReads,
    days: int = Query(7, ge=1, le=90),
    provider: str | None = Query(None, min_length=1, max_length=50),
) -> GatewayModelUsageSummaryResponse:
    """按当前团队注册模型名与请求日志 ``route_name`` 对齐；见 ``UsageAggregation`` 文档。"""
    raw = await reads.aggregate_gateway_model_route_usage(team, days=days, provider=provider)
    return GatewayModelUsageSummaryResponse.model_validate(raw)


@router.get("/admin/credential-stats", response_model=list[PlatformCredentialStatItem])
async def admin_credential_stats(
    team: CurrentTeam,
    reads: MgmtReads,
    days: int = Query(7, ge=1, le=90),
) -> list[PlatformCredentialStatItem]:
    if not team.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform admin can view credential stats",
        )
    rows = await reads.list_platform_credential_stats(days=days)
    return [PlatformCredentialStatItem.model_validate(r) for r in rows]


@router.post("/models", response_model=GatewayModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: GatewayModelCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> GatewayModelResponse:
    try:
        model = await writes.create_gateway_model(
            tenant_id=team.team_id,
            name=body.name,
            capability=body.capability,
            real_model=body.real_model,
            credential_id=body.credential_id,
            provider=body.provider,
            weight=body.weight,
            rpm_limit=body.rpm_limit,
            tpm_limit=body.tpm_limit,
            tags=body.tags,
            is_platform_admin=team.is_platform_admin,
            enabled=body.enabled,
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return GatewayModelResponse.model_validate(tenant_scoped_orm_dict(model))


@router.post(
    "/models/multi-credential",
    response_model=MultiCredentialGatewayModelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_multi_credential_model(
    body: MultiCredentialGatewayModelCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> MultiCredentialGatewayModelResponse:
    """同 ``(provider, real_model)`` 多凭据一键注册 + 自动 ``GatewayRoute``，启用 Router 负载均衡。"""
    try:
        result = await writes.create_multi_credential_gateway_model(
            tenant_id=team.team_id,
            name=body.name,
            capability=body.capability,
            real_model=body.real_model,
            provider=body.provider,
            credential_ids=list(body.credential_ids),
            is_platform_admin=team.is_platform_admin,
            strategy=body.strategy.value,
            weight=body.weight,
            rpm_limit=body.rpm_limit,
            tpm_limit=body.tpm_limit,
            tags=body.tags,
            enabled=body.enabled,
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
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
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> GatewayModelResponse:
    try:
        updated = await writes.update_gateway_model(
            model_id,
            tenant_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return GatewayModelResponse.model_validate(tenant_scoped_orm_dict(updated))


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_gateway_model(model_id, tenant_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.post("/models/{model_id}/test", response_model=GatewayModelTestResponse)
async def test_model(
    model_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> GatewayModelTestResponse:
    """对 Gateway 团队模型发起一次最小调用做连通性测试（chat / embedding / 生图）。

    成功/失败均返回 200 + ``success`` 字段，结果同步落库（``last_test_status``
    / ``last_tested_at``），列表页可直接通过 invalidate ``GET /models`` 刷新。
    """
    try:
        result = await writes.test_gateway_model(model_id, tenant_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return GatewayModelTestResponse.model_validate(result)


__all__ = ["router"]
