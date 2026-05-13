"""
Gateway Management Router (/api/v1/gateway/*)

提供：
- /keys       虚拟 Key 列表/创建/撤销
- /credentials 凭据 CRUD + 导入
- /models     模型注册表
- /routes     路由配置
- /budgets    预算管理
- /logs       调用日志查询
- /dashboard  仪表盘汇总 + 时序
- /alerts     告警规则与事件

团队 CRUD 与成员见 ``domains.tenancy.presentation.teams_router``（同前缀挂载）。

RBAC 矩阵见 plan：
- 平台 admin：全部
- team owner：自团队全部
- team admin：成员管理外的写操作
- team member：自己创建的资源 + 只读
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from bootstrap.config_loader import get_app_config
from domains.gateway.application.config_catalog_sync import (
    MANAGED_BY_KEY,
    MANAGED_CONFIG,
    sync_app_config_gateway_catalog,
)
from domains.gateway.application.management import (
    GatewayManagementReadService,
    GatewayManagementWriteService,
)
from domains.gateway.domain.usage_read_model import UsageAggregation
from domains.gateway.domain.virtual_key_service import (
    generate_vkey,
)
from domains.gateway.infrastructure.router_singleton import reload_router
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
    RequiredTeamMember,
)
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    BudgetResponse,
    BudgetUpsert,
    CredentialCreate,
    CredentialResponse,
    CredentialUpdate,
    DashboardSummaryResponse,
    GatewayModelCreate,
    GatewayModelPresetResponse,
    GatewayModelResponse,
    GatewayModelUpdate,
    RequestLogListResponse,
    RequestLogResponse,
    RouteCreate,
    RouteResponse,
    RouteUpdate,
    VirtualKeyCreate,
    VirtualKeyCreateResponse,
    VirtualKeyResponse,
)
from domains.identity.presentation.deps import AdminUser
from libs.crypto import derive_encryption_key, encrypt_value
from libs.db.database import get_db
from libs.exceptions import HttpMappableDomainError

router = APIRouter(prefix="/api/v1/gateway", tags=["AI Gateway"])


def _gateway_management_reads(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementReadService:
    return GatewayManagementReadService(db)


def _gateway_management_writes(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementWriteService:
    return GatewayManagementWriteService(db)


MgmtReads = Annotated[
    GatewayManagementReadService, Depends(_gateway_management_reads)
]
MgmtWrites = Annotated[
    GatewayManagementWriteService, Depends(_gateway_management_writes)
]


def _encryption_key() -> str:
    return derive_encryption_key(settings.secret_key.get_secret_value())


def _vkey_to_response(record: Any) -> VirtualKeyResponse:
    return VirtualKeyResponse(
        id=record.id,
        team_id=record.team_id,
        name=record.name,
        description=record.description,
        masked_key=record.masked_key_display,
        allowed_models=list(record.allowed_models or []),
        allowed_capabilities=list(record.allowed_capabilities or []),
        rpm_limit=record.rpm_limit,
        tpm_limit=record.tpm_limit,
        store_full_messages=record.store_full_messages,
        guardrail_enabled=record.guardrail_enabled,
        is_system=record.is_system,
        is_active=record.is_active,
        expires_at=record.expires_at,
        last_used_at=record.last_used_at,
        usage_count=record.usage_count,
        created_at=record.created_at,
    )


# =============================================================================
# Virtual Keys
# =============================================================================


@router.get("/keys", response_model=list[VirtualKeyResponse])
async def list_keys(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[VirtualKeyResponse]:
    keys = await reads.list_virtual_keys_for_team(team.team_id)
    return [_vkey_to_response(k) for k in keys]


@router.post("/keys", response_model=VirtualKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: VirtualKeyCreate,
    team: RequiredTeamMember,
    writes: MgmtWrites,
) -> VirtualKeyCreateResponse:
    plain, key_id_str, key_hash = generate_vkey()
    encrypted = encrypt_value(plain, _encryption_key())
    expires_at = (
        datetime.now(UTC) + timedelta(days=body.expires_in_days) if body.expires_in_days else None
    )
    record = await writes.create_virtual_key(
        team_id=team.team_id,
        created_by_user_id=team.user_id,
        name=body.name,
        description=body.description,
        key_id_str=key_id_str,
        key_hash=key_hash,
        encrypted_key=encrypted,
        allowed_models=body.allowed_models,
        allowed_capabilities=body.allowed_capabilities,
        rpm_limit=body.rpm_limit,
        tpm_limit=body.tpm_limit,
        store_full_messages=body.store_full_messages,
        guardrail_enabled=body.guardrail_enabled,
        expires_at=expires_at,
    )
    base = _vkey_to_response(record).model_dump()
    return VirtualKeyCreateResponse(**base, plain_key=plain)


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: uuid.UUID,
    team: RequiredTeamMember,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.revoke_virtual_key(
            key_id,
            team_id=team.team_id,
            actor_user_id=team.user_id,
            team_role=team.team_role,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


# =============================================================================
# Credentials
# =============================================================================


@router.get("/credentials", response_model=list[CredentialResponse])
async def list_credentials(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[CredentialResponse]:
    creds = await reads.list_credentials_for_team(
        team.team_id, include_system=team.is_platform_admin
    )
    return [CredentialResponse.model_validate(c) for c in creds]


@router.post("/credentials", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> CredentialResponse:
    encrypted = encrypt_value(body.api_key, _encryption_key())
    cred = await writes.create_team_credential(
        team_id=team.team_id,
        provider=body.provider,
        name=body.name,
        api_key_encrypted=encrypted,
        api_base=body.api_base,
        extra=body.extra,
    )
    return CredentialResponse.model_validate(cred)


@router.patch("/credentials/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> CredentialResponse:
    try:
        encrypted = (
            encrypt_value(body.api_key, _encryption_key()) if body.api_key else None
        )
        updated = await writes.update_team_credential(
            credential_id,
            team_id=team.team_id,
            api_key_encrypted=encrypted,
            api_base=body.api_base,
            extra=body.extra,
            is_active=body.is_active,
            name=body.name,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return CredentialResponse.model_validate(updated)


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_team_credential(credential_id, team_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.post(
    "/credentials/import-from-user",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_user_credential(
    body: dict[str, uuid.UUID],
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> CredentialResponse:
    """从用户私有凭据导入到当前团队"""
    user_credential_id = body.get("credential_id")
    if user_credential_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "credential_id required")
    try:
        new_cred = await writes.import_user_credential_to_team(
            user_credential_id=user_credential_id,
            team_id=team.team_id,
            actor_user_id=team.user_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return CredentialResponse.model_validate(new_cred)


@router.post("/credentials/import")
async def import_all_user_credentials(
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> dict[str, int]:
    """一键把当前用户的所有 user-scope 凭据导入到当前团队（只复制不删除原凭据）"""
    if team.user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User context required")
    created = await writes.import_all_user_credentials_to_team(
        actor_user_id=team.user_id,
        team_id=team.team_id,
    )
    return {"created": created}


# =============================================================================
# Models
# =============================================================================


def _infer_preset_capability(model: Any) -> str:
    if getattr(model, "supports_image_gen", False):
        return "image"
    if "embedding" in model.id:
        return "embedding"
    return "chat"


@router.get("/models/presets", response_model=list[GatewayModelPresetResponse])
async def list_model_presets(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[GatewayModelPresetResponse]:
    """返回已同步到 DB 的配置托管全局模型目录；若无则回退 app.toml（兼容旧环境）。"""
    _ = team
    models = await reads.list_gateway_models(team.team_id, only_enabled=True)
    cfg_rows = [
        m
        for m in models
        if m.team_id is None and (m.tags or {}).get(MANAGED_BY_KEY) == MANAGED_CONFIG
    ]
    if cfg_rows:
        return [
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
            )
            for m in cfg_rows
        ]
    return [
        GatewayModelPresetResponse(
            id=model.id,
            name=model.name,
            provider=model.provider,
            real_model=model.litellm_model or model.id,
            capability=_infer_preset_capability(model),
            context_window=model.context_window,
            input_price=model.input_price,
            output_price=model.output_price,
            supports_vision=model.supports_vision,
            supports_tools=model.supports_tools,
            supports_reasoning=model.supports_reasoning,
            recommended_for=list(model.recommended_for),
            description=model.description,
        )
        for model in get_app_config().models.available
        if model.litellm_model or model.id
    ]


@router.post("/catalog/reload-from-config")
async def reload_gateway_catalog_from_config(
    _: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """平台管理员：从 app.toml 重新同步全局模型目录并重载 LiteLLM Router。"""
    stats = await sync_app_config_gateway_catalog(db)
    await db.commit()
    await reload_router(db)
    return {"ok": True, **stats}


@router.get("/models", response_model=list[GatewayModelResponse])
async def list_models(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[GatewayModelResponse]:
    models = await reads.list_gateway_models(team.team_id, only_enabled=False)
    return [GatewayModelResponse.model_validate(m) for m in models]


@router.post("/models", response_model=GatewayModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: GatewayModelCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> GatewayModelResponse:
    model = await writes.create_gateway_model(
        team_id=team.team_id,
        name=body.name,
        capability=body.capability,
        real_model=body.real_model,
        credential_id=body.credential_id,
        provider=body.provider,
        weight=body.weight,
        rpm_limit=body.rpm_limit,
        tpm_limit=body.tpm_limit,
        tags=body.tags,
    )
    return GatewayModelResponse.model_validate(model)


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
            team_id=team.team_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return GatewayModelResponse.model_validate(updated)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_gateway_model(model_id, team_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


# =============================================================================
# Routes
# =============================================================================


@router.get("/routes", response_model=list[RouteResponse])
async def list_routes(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[RouteResponse]:
    routes = await reads.list_gateway_routes(team.team_id, only_enabled=False)
    return [RouteResponse.model_validate(r) for r in routes]


@router.post("/routes", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: RouteCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> RouteResponse:
    route = await writes.create_gateway_route(
        team_id=team.team_id,
        virtual_model=body.virtual_model,
        primary_models=body.primary_models,
        fallbacks_general=body.fallbacks_general,
        fallbacks_content_policy=body.fallbacks_content_policy,
        fallbacks_context_window=body.fallbacks_context_window,
        strategy=body.strategy,
        retry_policy=body.retry_policy,
    )
    await writes.reload_litellm_router()
    return RouteResponse.model_validate(route)


@router.patch("/routes/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: uuid.UUID,
    body: RouteUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> RouteResponse:
    try:
        updated = await writes.update_gateway_route(
            route_id,
            team_id=team.team_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    await writes.reload_litellm_router()
    return RouteResponse.model_validate(updated)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_gateway_route(route_id, team_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    await writes.reload_litellm_router()


# =============================================================================
# Budgets
# =============================================================================


@router.get("/budgets", response_model=list[BudgetResponse])
async def list_budgets(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[BudgetResponse]:
    budgets = await reads.list_budgets_for_team_and_user(team.team_id, team.user_id)
    return [BudgetResponse.model_validate(b) for b in budgets]


@router.put("/budgets", response_model=BudgetResponse)
async def upsert_budget(
    body: BudgetUpsert,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> BudgetResponse:
    if body.scope == "team":
        body.scope_id = team.team_id
    if body.scope == "user" and body.scope_id is None:
        body.scope_id = team.user_id
    if body.scope == "key" and body.scope_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "key scope requires scope_id")
    if body.scope == "system" and not team.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only platform admin can set system budget")
    budget = await writes.upsert_budget(
        scope=body.scope,
        scope_id=body.scope_id,
        period=body.period,
        limit_usd=body.limit_usd,
        limit_tokens=body.limit_tokens,
        limit_requests=body.limit_requests,
    )
    return BudgetResponse.model_validate(budget)


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    await writes.delete_budget(budget_id)


# =============================================================================
# Logs
# =============================================================================


@router.get("/logs", response_model=RequestLogListResponse)
async def list_logs(
    team: CurrentTeam,
    reads: MgmtReads,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=(
            "用量切片：workspace=按当前 X-Team-Id 工作区（含 personal/shared）；"
            "user=按当前登录用户跨工作区。"
        ),
    ),
    start: datetime | None = None,
    end: datetime | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    capability: str | None = None,
    vkey_id: uuid.UUID | None = None,
) -> RequestLogListResponse:
    items, total = await reads.list_request_logs(
        team,
        usage_aggregation=usage_aggregation,
        page=page,
        page_size=page_size,
        start=start,
        end=end,
        status_filter=status_filter,
        capability=capability,
        vkey_id=vkey_id,
    )
    return RequestLogListResponse(
        items=[RequestLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/{log_id}", response_model=RequestLogResponse)
async def get_log_detail(
    log_id: uuid.UUID,
    team: CurrentTeam,
    reads: MgmtReads,
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=(
            "用量切片：workspace=按当前工作区 team_id；user=仅当日志 user_id 为当前用户时可见。"
        ),
    ),
) -> RequestLogResponse:
    try:
        record = await reads.get_request_log(
            team, log_id, usage_aggregation=usage_aggregation
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Log not found")
    return RequestLogResponse.model_validate(record)


# =============================================================================
# Dashboard
# =============================================================================


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def dashboard_summary(
    team: CurrentTeam,
    reads: MgmtReads,
    days: int = Query(7, ge=1, le=90),
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=(
            "用量切片：workspace=按当前工作区聚合；user=按当前用户跨工作区聚合。"
        ),
    ),
) -> DashboardSummaryResponse:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    summary = await reads.aggregate_request_log_summary(
        team, start, end, usage_aggregation=usage_aggregation
    )
    total = summary["total"]
    success = summary["success"]
    return DashboardSummaryResponse(
        total_requests=total,
        total_input_tokens=summary["input_tokens"],
        total_output_tokens=summary["output_tokens"],
        total_cost_usd=summary["cost_usd"],
        success_count=success,
        failure_count=summary["failure"],
        avg_latency_ms=summary["avg_latency_ms"],
        success_rate=(success / total) if total else 0.0,
    )


# =============================================================================
# Alerts
# =============================================================================


@router.get("/alerts/rules", response_model=list[AlertRuleResponse])
async def list_alert_rules(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[AlertRuleResponse]:
    rows = await reads.list_alert_rules(team.team_id)
    return [AlertRuleResponse.model_validate(r) for r in rows]


@router.post("/alerts/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    body: AlertRuleCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> AlertRuleResponse:
    rule = await writes.create_alert_rule(
        team_id=team.team_id,
        name=body.name,
        description=body.description,
        metric=body.metric,
        threshold=Decimal(str(body.threshold)),
        window_minutes=body.window_minutes,
        channels=body.channels,
        enabled=body.enabled,
    )
    return AlertRuleResponse.model_validate(rule)


@router.patch("/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: uuid.UUID,
    body: AlertRuleUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> AlertRuleResponse:
    try:
        rule = await writes.update_alert_rule(
            rule_id,
            team_id=team.team_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return AlertRuleResponse.model_validate(rule)


@router.delete("/alerts/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_alert_rule(rule_id, team_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.get("/alerts/events", response_model=list[Any])
async def list_alert_events(
    team: CurrentTeam,
    reads: MgmtReads,
    limit: int = Query(100, ge=1, le=500),
) -> list[Any]:
    return await reads.list_alert_events_as_dicts(team.team_id, limit=limit)


__all__ = ["router"]
