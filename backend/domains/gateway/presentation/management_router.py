"""
Gateway Management Router (/api/v1/gateway/*)

提供：
- /teams      团队 CRUD + 成员
- /keys       虚拟 Key 列表/创建/撤销
- /credentials 凭据 CRUD + 导入
- /models     模型注册表
- /routes     路由配置
- /budgets    预算管理
- /logs       调用日志查询
- /dashboard  仪表盘汇总 + 时序
- /alerts     告警规则与事件

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
from domains.gateway.application.commands.gateway_management_commands import (
    GatewayManagementCommandService,
)
from domains.gateway.application.queries.gateway_management_queries import (
    GatewayManagementQueryService,
)
from domains.gateway.application.team_service import TeamService
from domains.gateway.domain.errors import GatewayError
from domains.gateway.domain.virtual_key_service import (
    generate_vkey,
)
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
    RequiredTeamMember,
    RequiredTeamOwner,
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
    TeamCreate,
    TeamMemberAdd,
    TeamMemberResponse,
    TeamResponse,
    TeamUpdate,
    VirtualKeyCreate,
    VirtualKeyCreateResponse,
    VirtualKeyResponse,
)
from domains.identity.presentation.deps import RequiredAuthUser
from libs.crypto import derive_encryption_key, encrypt_value
from libs.db.database import get_db

router = APIRouter(prefix="/api/v1/gateway", tags=["AI Gateway"])


def _gateway_management_queries(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementQueryService:
    return GatewayManagementQueryService(db)


def _gateway_management_commands(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementCommandService:
    return GatewayManagementCommandService(db)


MgmtQueries = Annotated[
    GatewayManagementQueryService, Depends(_gateway_management_queries)
]
MgmtCommands = Annotated[
    GatewayManagementCommandService, Depends(_gateway_management_commands)
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
# Teams
# =============================================================================


@router.get("/teams", response_model=list[TeamResponse])
async def list_my_teams(
    current_user: RequiredAuthUser,
    queries: MgmtQueries,
) -> list[TeamResponse]:
    user_uuid = uuid.UUID(current_user.id)
    items_data = await queries.list_teams_with_roles_for_user(user_uuid)
    out: list[TeamResponse] = []
    for t, role in items_data:
        resp = TeamResponse.model_validate(t)
        resp.team_role = role
        out.append(resp)
    return out


@router.post("/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreate,
    current_user: RequiredAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamResponse:
    if current_user.is_anonymous:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Anonymous cannot create team")
    team = await TeamService(db).create_team(
        name=body.name,
        owner_user_id=uuid.UUID(current_user.id),
        slug=body.slug,
        settings=body.settings,
    )
    return TeamResponse.model_validate(team)


@router.patch("/teams/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdate,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> TeamResponse:
    updated = await commands.update_team(
        team_id, name=body.name, settings=body.settings
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return TeamResponse.model_validate(updated)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    team: RequiredTeamOwner,
    queries: MgmtQueries,
    commands: MgmtCommands,
) -> None:
    record = await queries.get_team(team_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    if record.kind == "personal":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete personal team")
    try:
        await commands.delete_shared_team(team_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/teams/{team_id}/members", response_model=list[TeamMemberResponse])
async def list_team_members(
    team_id: uuid.UUID,
    team: RequiredTeamMember,
    queries: MgmtQueries,
) -> list[TeamMemberResponse]:
    members = await queries.list_team_members(team_id)
    return [TeamMemberResponse.model_validate(m) for m in members]


@router.post("/teams/{team_id}/members", response_model=TeamMemberResponse)
async def add_team_member(
    team_id: uuid.UUID,
    body: TeamMemberAdd,
    team: RequiredTeamAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TeamMemberResponse:
    member = await TeamService(db).add_member(team_id, body.user_id, body.role)
    return TeamMemberResponse.model_validate(member)


@router.delete("/teams/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    team: RequiredTeamAdmin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await TeamService(db).remove_member(team_id, user_id)


# =============================================================================
# Virtual Keys
# =============================================================================


@router.get("/keys", response_model=list[VirtualKeyResponse])
async def list_keys(
    team: CurrentTeam,
    queries: MgmtQueries,
) -> list[VirtualKeyResponse]:
    keys = await queries.list_virtual_keys_for_team(team.team_id)
    return [_vkey_to_response(k) for k in keys]


@router.post("/keys", response_model=VirtualKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: VirtualKeyCreate,
    team: RequiredTeamMember,
    commands: MgmtCommands,
) -> VirtualKeyCreateResponse:
    plain, key_id_str, key_hash = generate_vkey()
    encrypted = encrypt_value(plain, _encryption_key())
    expires_at = (
        datetime.now(UTC) + timedelta(days=body.expires_in_days) if body.expires_in_days else None
    )
    record = await commands.create_virtual_key(
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
    commands: MgmtCommands,
) -> None:
    try:
        await commands.revoke_virtual_key(
            key_id,
            team_id=team.team_id,
            actor_user_id=team.user_id,
            team_role=team.team_role,
            is_platform_admin=team.is_platform_admin,
        )
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


# =============================================================================
# Credentials
# =============================================================================


@router.get("/credentials", response_model=list[CredentialResponse])
async def list_credentials(
    team: CurrentTeam,
    queries: MgmtQueries,
) -> list[CredentialResponse]:
    creds = await queries.list_credentials_for_team(
        team.team_id, include_system=team.is_platform_admin
    )
    return [CredentialResponse.model_validate(c) for c in creds]


@router.post("/credentials", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialCreate,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> CredentialResponse:
    encrypted = encrypt_value(body.api_key, _encryption_key())
    cred = await commands.create_team_credential(
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
    commands: MgmtCommands,
) -> CredentialResponse:
    try:
        encrypted = (
            encrypt_value(body.api_key, _encryption_key()) if body.api_key else None
        )
        updated = await commands.update_team_credential(
            credential_id,
            team_id=team.team_id,
            api_key_encrypted=encrypted,
            api_base=body.api_base,
            extra=body.extra,
            is_active=body.is_active,
            name=body.name,
        )
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return CredentialResponse.model_validate(updated)


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> None:
    try:
        await commands.delete_team_credential(credential_id, team_id=team.team_id)
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.post(
    "/credentials/import-from-user",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_user_credential(
    body: dict[str, uuid.UUID],
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> CredentialResponse:
    """从用户私有凭据导入到当前团队"""
    user_credential_id = body.get("credential_id")
    if user_credential_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "credential_id required")
    try:
        new_cred = await commands.import_user_credential_to_team(
            user_credential_id=user_credential_id,
            team_id=team.team_id,
            actor_user_id=team.user_id,
            is_platform_admin=team.is_platform_admin,
        )
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return CredentialResponse.model_validate(new_cred)


@router.post("/credentials/import")
async def import_all_user_credentials(
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> dict[str, int]:
    """一键把当前用户的所有 user-scope 凭据导入到当前团队（只复制不删除原凭据）"""
    if team.user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User context required")
    created = await commands.import_all_user_credentials_to_team(
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
) -> list[GatewayModelPresetResponse]:
    """返回系统配置中的常用模型目录，供 Gateway 页面快速注册。"""
    _ = team
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


@router.get("/models", response_model=list[GatewayModelResponse])
async def list_models(
    team: CurrentTeam,
    queries: MgmtQueries,
) -> list[GatewayModelResponse]:
    models = await queries.list_gateway_models(team.team_id, only_enabled=False)
    return [GatewayModelResponse.model_validate(m) for m in models]


@router.post("/models", response_model=GatewayModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(
    body: GatewayModelCreate,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> GatewayModelResponse:
    model = await commands.create_gateway_model(
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
    commands: MgmtCommands,
) -> GatewayModelResponse:
    try:
        updated = await commands.update_gateway_model(
            model_id,
            team_id=team.team_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return GatewayModelResponse.model_validate(updated)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: uuid.UUID,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> None:
    try:
        await commands.delete_gateway_model(model_id, team_id=team.team_id)
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


# =============================================================================
# Routes
# =============================================================================


@router.get("/routes", response_model=list[RouteResponse])
async def list_routes(
    team: CurrentTeam,
    queries: MgmtQueries,
) -> list[RouteResponse]:
    routes = await queries.list_gateway_routes(team.team_id, only_enabled=False)
    return [RouteResponse.model_validate(r) for r in routes]


@router.post("/routes", response_model=RouteResponse, status_code=status.HTTP_201_CREATED)
async def create_route(
    body: RouteCreate,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> RouteResponse:
    route = await commands.create_gateway_route(
        team_id=team.team_id,
        virtual_model=body.virtual_model,
        primary_models=body.primary_models,
        fallbacks_general=body.fallbacks_general,
        fallbacks_content_policy=body.fallbacks_content_policy,
        fallbacks_context_window=body.fallbacks_context_window,
        strategy=body.strategy,
        retry_policy=body.retry_policy,
    )
    await commands.reload_litellm_router()
    return RouteResponse.model_validate(route)


@router.patch("/routes/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: uuid.UUID,
    body: RouteUpdate,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> RouteResponse:
    try:
        updated = await commands.update_gateway_route(
            route_id,
            team_id=team.team_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    await commands.reload_litellm_router()
    return RouteResponse.model_validate(updated)


@router.delete("/routes/{route_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(
    route_id: uuid.UUID,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> None:
    try:
        await commands.delete_gateway_route(route_id, team_id=team.team_id)
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    await commands.reload_litellm_router()


# =============================================================================
# Budgets
# =============================================================================


@router.get("/budgets", response_model=list[BudgetResponse])
async def list_budgets(
    team: CurrentTeam,
    queries: MgmtQueries,
) -> list[BudgetResponse]:
    budgets = await queries.list_budgets_for_team_and_user(team.team_id, team.user_id)
    return [BudgetResponse.model_validate(b) for b in budgets]


@router.put("/budgets", response_model=BudgetResponse)
async def upsert_budget(
    body: BudgetUpsert,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> BudgetResponse:
    if body.scope == "team":
        body.scope_id = team.team_id
    if body.scope == "user" and body.scope_id is None:
        body.scope_id = team.user_id
    if body.scope == "key" and body.scope_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "key scope requires scope_id")
    if body.scope == "system" and not team.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only platform admin can set system budget")
    budget = await commands.upsert_budget(
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
    commands: MgmtCommands,
) -> None:
    await commands.delete_budget(budget_id)


# =============================================================================
# Logs
# =============================================================================


@router.get("/logs", response_model=RequestLogListResponse)
async def list_logs(
    team: CurrentTeam,
    queries: MgmtQueries,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    start: datetime | None = None,
    end: datetime | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    capability: str | None = None,
    vkey_id: uuid.UUID | None = None,
) -> RequestLogListResponse:
    items, total = await queries.list_request_logs(
        team,
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
    queries: MgmtQueries,
) -> RequestLogResponse:
    try:
        record = await queries.get_request_log_for_team(team, log_id)
    except GatewayError as exc:
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
    queries: MgmtQueries,
    days: int = Query(7, ge=1, le=90),
) -> DashboardSummaryResponse:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    summary = await queries.aggregate_request_log_summary(team.team_id, start, end)
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
    queries: MgmtQueries,
) -> list[AlertRuleResponse]:
    rows = await queries.list_alert_rules(team.team_id)
    return [AlertRuleResponse.model_validate(r) for r in rows]


@router.post("/alerts/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    body: AlertRuleCreate,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> AlertRuleResponse:
    rule = await commands.create_alert_rule(
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
    commands: MgmtCommands,
) -> AlertRuleResponse:
    try:
        rule = await commands.update_alert_rule(
            rule_id,
            team_id=team.team_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return AlertRuleResponse.model_validate(rule)


@router.delete("/alerts/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    team: RequiredTeamAdmin,
    commands: MgmtCommands,
) -> None:
    try:
        await commands.delete_alert_rule(rule_id, team_id=team.team_id)
    except GatewayError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.get("/alerts/events", response_model=list[Any])
async def list_alert_events(
    team: CurrentTeam,
    queries: MgmtQueries,
    limit: int = Query(100, ge=1, le=500),
) -> list[Any]:
    return await queries.list_alert_events_as_dicts(team.team_id, limit=limit)


__all__ = ["router"]
