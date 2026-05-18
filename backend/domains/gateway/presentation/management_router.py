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
from domains.gateway.application.catalog_capability import infer_catalog_capability
from domains.gateway.application.config_catalog_sync import (
    MANAGED_BY_KEY,
    MANAGED_CONFIG,
    _build_tags_from_model_info,
    model_types_for_gateway_registration,
    selector_capabilities_from_tags,
    sync_app_config_gateway_catalog,
)
from domains.gateway.application.management import (
    GatewayManagementReadService,
    GatewayManagementWriteService,
)
from domains.gateway.application.management.credential_upstream_catalog import (
    CredentialUpstreamCatalogService,
)
from domains.gateway.application.management.usage_reads import MarginGroupBy
from domains.gateway.application.model_selector_reads import list_available_models
from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter
from domains.gateway.domain.credential_probe import CredentialProbeResult
from domains.gateway.domain.types import (
    MANAGED_GATEWAY_CREDENTIAL_PROVIDERS,
    PERSONAL_MODEL_PROVIDERS,
    USER_GATEWAY_CREDENTIAL_PROVIDERS,
)
from domains.gateway.domain.usage_read_model import UsageAggregation
from domains.gateway.domain.virtual_key_service import (
    generate_vkey,
)
from domains.gateway.infrastructure.models.entitlement_plan import (
    EntitlementPlan,
    EntitlementPlanQuota,
)
from domains.gateway.infrastructure.models.provider_plan import (
    ProviderPlan,
    ProviderPlanQuota,
)
from domains.gateway.presentation.credential_response import (
    build_credential_response,
    decrypt_credential_api_key_for_reveal,
)
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
    RequiredTeamMember,
)
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    AlertEventResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    BudgetResponse,
    BudgetUpsert,
    CredentialResponse,
    CredentialUpdate,
    DashboardSummaryResponse,
    EntitlementPlanCreate,
    EntitlementPlanQuotaResponse,
    EntitlementPlanResponse,
    EntitlementPlanUpdate,
    EntitlementUsageResponse,
    GatewayModelCreate,
    GatewayModelPresetResponse,
    GatewayModelResponse,
    GatewayModelTestResponse,
    GatewayModelUpdate,
    GatewayModelUsageSummaryResponse,
    ManagedCredentialCreate,
    MarginGroupItemResponse,
    MarginSummaryResponse,
    PersonalModelCreate,
    PersonalModelResponse,
    PersonalModelUpdate,
    PlanQuotaResponse,
    PlatformCredentialStatItem,
    ProviderPlanCostResponse,
    ProviderPlanCreate,
    ProviderPlanResponse,
    ProviderPlanUpdate,
    RequestLogDetailResponse,
    RequestLogListResponse,
    RequestLogResponse,
    RouteCreate,
    RouteResponse,
    RouteUpdate,
    UserCredentialCreate,
    VirtualKeyCreate,
    VirtualKeyCreateResponse,
    VirtualKeyResponse,
)
from domains.gateway.presentation.schemas.credential_upstream_catalog import (
    BatchImportFailureItem,
    CredentialProbeResponse,
    PersonalModelBatchImportCreatedItem,
    PersonalModelBatchImportRequest,
    PersonalModelBatchImportResponse,
    TeamGatewayModelBatchImportCreatedItem,
    TeamGatewayModelBatchImportRequest,
    TeamGatewayModelBatchImportResponse,
    UpstreamModelItemResponse,
)
from domains.identity.presentation.deps import (
    AdminUser,
    OptionalAuthUser,
    RequiredAuthUser,
    get_owned_user_ids,
    get_user_uuid,
)
from libs.crypto import derive_encryption_key, encrypt_value
from libs.db.database import get_db
from libs.exceptions import HttpMappableDomainError, ValidationError

router = APIRouter(prefix="/api/v1/gateway", tags=["AI Gateway"])


def _credential_probe_to_response(result: CredentialProbeResult) -> CredentialProbeResponse:
    return CredentialProbeResponse(
        credential_id=result.credential_id,
        probe_at=result.probe_at,
        support=result.support,
        upstream=result.upstream,
        items=[
            UpstreamModelItemResponse(id=i.id, owned_by=i.owned_by) for i in result.items
        ],
        message=result.message,
        http_status=result.http_status,
    )


def _validate_user_credential_provider(provider: str) -> str:
    p = provider.lower()
    if p not in USER_GATEWAY_CREDENTIAL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"不支持的提供商: {provider}。"
                f"支持: {', '.join(sorted(USER_GATEWAY_CREDENTIAL_PROVIDERS))}"
            ),
        )
    return p


def _validate_managed_credential_provider(provider: str) -> str:
    """校验 team/system 凭据 provider；与前端 `provider-schemas.ts` 表对齐。"""
    p = provider.lower()
    if p not in MANAGED_GATEWAY_CREDENTIAL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"不支持的提供商: {provider}。"
                f"支持: {', '.join(sorted(MANAGED_GATEWAY_CREDENTIAL_PROVIDERS))}"
            ),
        )
    return p


def _validate_personal_model_provider(provider: str) -> str:
    p = provider.lower()
    if p not in PERSONAL_MODEL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"不支持的提供商: {provider}。"
                f"支持: {', '.join(sorted(PERSONAL_MODEL_PROVIDERS))}"
            ),
        )
    return p


def _gateway_management_reads(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementReadService:
    return GatewayManagementReadService(db)


def _gateway_management_writes(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementWriteService:
    return GatewayManagementWriteService(db)


MgmtReads = Annotated[GatewayManagementReadService, Depends(_gateway_management_reads)]
MgmtWrites = Annotated[GatewayManagementWriteService, Depends(_gateway_management_writes)]


def _credential_upstream_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialUpstreamCatalogService:
    return CredentialUpstreamCatalogService(db)


CatalogSvc = Annotated[CredentialUpstreamCatalogService, Depends(_credential_upstream_catalog)]


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
    return [build_credential_response(c, encryption_key=_encryption_key()) for c in creds]


@router.get("/credentials/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> CredentialResponse:
    try:
        row = await reads.get_managed_credential_for_team(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return build_credential_response(row, encryption_key=_encryption_key())


@router.get("/credentials/{credential_id}/reveal", response_model=dict[str, str])
async def reveal_managed_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> dict[str, str]:
    """解密并返回完整 API Key（与 GET 凭据详情相同权限；用于前端显式展示）。"""
    try:
        row = await reads.get_managed_credential_for_team(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        plain = decrypt_credential_api_key_for_reveal(
            row,
            encryption_key=_encryption_key(),
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return {"api_key": plain}


@router.post("/credentials", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: ManagedCredentialCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> CredentialResponse:
    provider = _validate_managed_credential_provider(body.provider)
    encrypted = encrypt_value(body.api_key, _encryption_key())
    try:
        if body.scope == "system":
            cred = await writes.create_system_credential(
                is_platform_admin=team.is_platform_admin,
                provider=provider,
                name=body.name,
                api_key_encrypted=encrypted,
                api_base=body.api_base,
                extra=body.extra,
            )
        else:
            cred = await writes.create_team_credential(
                team_id=team.team_id,
                provider=provider,
                name=body.name,
                api_key_encrypted=encrypted,
                api_base=body.api_base,
                extra=body.extra,
            )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return build_credential_response(cred, encryption_key=_encryption_key())


@router.patch("/credentials/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> CredentialResponse:
    try:
        encrypted = encrypt_value(body.api_key, _encryption_key()) if body.api_key else None
        updated = await writes.update_managed_credential(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            api_key_encrypted=encrypted,
            api_base=body.api_base,
            extra=body.extra,
            is_active=body.is_active,
            name=body.name,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return build_credential_response(updated, encryption_key=_encryption_key())


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_managed_credential(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.post("/credentials/{credential_id}/probe", response_model=CredentialProbeResponse)
async def probe_managed_credential_endpoint(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    catalog: CatalogSvc,
) -> CredentialProbeResponse:
    """POST 触发上游 OpenAI 兼容 ``/v1/models`` 列举（同路径重复调用即刷新）。"""
    try:
        result = await catalog.probe_managed_credential(
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            credential_id=credential_id,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return _credential_probe_to_response(result)


@router.post(
    "/credentials/{credential_id}/batch-import-models",
    response_model=TeamGatewayModelBatchImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def batch_import_team_models_endpoint(
    credential_id: uuid.UUID,
    body: TeamGatewayModelBatchImportRequest,
    team: RequiredTeamAdmin,
    catalog: CatalogSvc,
) -> TeamGatewayModelBatchImportResponse:
    try:
        tuples = [(it.upstream_model_id, it.name) for it in body.items]
        created_raw, failed_raw = await catalog.batch_import_team_models(
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            credential_id=credential_id,
            provider=body.provider.strip().lower(),
            capability=body.capability,
            weight=body.weight,
            rpm_limit=body.rpm_limit,
            tpm_limit=body.tpm_limit,
            tags=body.tags,
            enabled=body.enabled,
            items=tuples,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return TeamGatewayModelBatchImportResponse(
        credential_id=credential_id,
        created=[
            TeamGatewayModelBatchImportCreatedItem(
                upstream_model_id=c["upstream_model_id"],
                gateway_model_id=c["gateway_model_id"],
            )
            for c in created_raw
        ],
        failed=[BatchImportFailureItem.model_validate(f) for f in failed_raw],
    )


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
    return build_credential_response(new_cred, encryption_key=_encryption_key())


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
# User-scoped credentials (JWT only; no X-Team-Id)
# =============================================================================


@router.get("/my-credentials", response_model=list[CredentialResponse])
async def list_my_credentials(
    current_user: RequiredAuthUser,
    reads: MgmtReads,
) -> list[CredentialResponse]:
    user_id = get_user_uuid(current_user)
    creds = await reads.list_user_credentials(user_id)
    return [build_credential_response(c, encryption_key=_encryption_key()) for c in creds]


@router.get("/my-credentials/{credential_id}/reveal", response_model=dict[str, str])
async def reveal_my_credential(
    credential_id: uuid.UUID,
    current_user: RequiredAuthUser,
    reads: MgmtReads,
) -> dict[str, str]:
    """解密并返回当前用户私有凭据的完整 API Key。"""
    user_id = get_user_uuid(current_user)
    try:
        row = await reads.get_user_credential_for_owner(credential_id, user_id)
        plain = decrypt_credential_api_key_for_reveal(
            row,
            encryption_key=_encryption_key(),
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return {"api_key": plain}


@router.post(
    "/my-credentials", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED
)
async def create_my_credential(
    body: UserCredentialCreate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> CredentialResponse:
    user_id = get_user_uuid(current_user)
    provider = _validate_user_credential_provider(body.provider)
    encrypted = encrypt_value(body.api_key, _encryption_key())
    try:
        cred = await writes.create_user_credential(
            actor_user_id=user_id,
            provider=provider,
            name=body.name.strip() or "default",
            api_key_encrypted=encrypted,
            api_base=body.api_base,
            extra=body.extra,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return build_credential_response(cred, encryption_key=_encryption_key())


@router.patch("/my-credentials/{credential_id}", response_model=CredentialResponse)
async def update_my_credential(
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> CredentialResponse:
    user_id = get_user_uuid(current_user)
    try:
        encrypted = encrypt_value(body.api_key, _encryption_key()) if body.api_key else None
        updated = await writes.update_user_credential(
            credential_id,
            actor_user_id=user_id,
            api_key_encrypted=encrypted,
            api_base=body.api_base,
            extra=body.extra,
            is_active=body.is_active,
            name=body.name,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return build_credential_response(updated, encryption_key=_encryption_key())


@router.delete("/my-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_credential(
    credential_id: uuid.UUID,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> None:
    user_id = get_user_uuid(current_user)
    try:
        await writes.delete_user_credential(credential_id, actor_user_id=user_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.post("/my-credentials/{credential_id}/probe", response_model=CredentialProbeResponse)
async def probe_my_credential_endpoint(
    credential_id: uuid.UUID,
    current_user: RequiredAuthUser,
    catalog: CatalogSvc,
) -> CredentialProbeResponse:
    """POST 触发上游列举；重复调用即刷新。"""
    user_id = get_user_uuid(current_user)
    try:
        result = await catalog.probe_user_credential(user_id=user_id, credential_id=credential_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return _credential_probe_to_response(result)


@router.post(
    "/my-credentials/{credential_id}/batch-import-models",
    response_model=PersonalModelBatchImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def batch_import_my_models_endpoint(
    credential_id: uuid.UUID,
    body: PersonalModelBatchImportRequest,
    current_user: RequiredAuthUser,
    catalog: CatalogSvc,
) -> PersonalModelBatchImportResponse:
    user_id = get_user_uuid(current_user)
    provider = _validate_personal_model_provider(body.provider)
    try:
        created_raw, failed_raw = await catalog.batch_import_personal_models(
            user_id=user_id,
            credential_id=credential_id,
            provider=provider,
            upstream_model_ids=body.upstream_model_ids,
            model_types=body.model_types,
            display_name_prefix=body.display_name_prefix,
            enabled=body.enabled,
            tags=body.tags,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return PersonalModelBatchImportResponse(
        credential_id=credential_id,
        created=[
            PersonalModelBatchImportCreatedItem(
                upstream_model_id=c["upstream_model_id"],
                gateway_model_ids=c["gateway_model_ids"],
            )
            for c in created_raw
        ],
        failed=[BatchImportFailureItem.model_validate(f) for f in failed_raw],
    )


# =============================================================================
# User-scoped personal models (JWT only; no X-Team-Id)
# =============================================================================


@router.get("/my-models", response_model=list[PersonalModelResponse])
async def list_my_models(
    current_user: RequiredAuthUser,
    reads: MgmtReads,
    provider: str | None = Query(None, min_length=1, max_length=50),
) -> list[PersonalModelResponse]:
    user_id = get_user_uuid(current_user)
    rows = await reads.list_personal_gateway_models(user_id, provider=provider)
    return [PersonalModelResponse.from_gateway_model(r) for r in rows]


@router.post(
    "/my-models",
    response_model=list[PersonalModelResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_my_models(
    body: PersonalModelCreate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> list[PersonalModelResponse]:
    user_id = get_user_uuid(current_user)
    provider = _validate_personal_model_provider(body.provider)
    try:
        rows = await writes.create_personal_models(
            user_id,
            display_name=body.display_name.strip(),
            provider=provider,
            model_id=body.model_id.strip(),
            credential_id=body.credential_id,
            model_types=body.model_types,
            tags=body.tags,
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return [PersonalModelResponse.from_gateway_model(r) for r in rows]


@router.patch("/my-models/{model_id}", response_model=PersonalModelResponse)
async def update_my_model(
    model_id: uuid.UUID,
    body: PersonalModelUpdate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> PersonalModelResponse:
    user_id = get_user_uuid(current_user)
    try:
        updated = await writes.update_personal_model(
            user_id,
            model_id,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return PersonalModelResponse.from_gateway_model(updated)


@router.delete("/my-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_model(
    model_id: uuid.UUID,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> None:
    user_id = get_user_uuid(current_user)
    try:
        await writes.delete_personal_model(user_id, model_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.post("/my-models/{model_id}/test", response_model=GatewayModelTestResponse)
async def test_my_model(
    model_id: uuid.UUID,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> GatewayModelTestResponse:
    user_id = get_user_uuid(current_user)
    try:
        result = await writes.test_personal_model(user_id, model_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return GatewayModelTestResponse.model_validate(result)


def _effective_model_type_query(*, model_type: str | None, mode: str | None) -> str | None:
    if model_type and model_type.strip():
        return model_type.strip()
    if not mode or not mode.strip():
        return None
    key = mode.strip().lower()
    return {"chat": "text", "image_gen": "image_gen", "video": "video"}.get(key)


def _validate_optional_provider(provider: str | None) -> None:
    if provider is not None and provider not in PERSONAL_MODEL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的提供商: {provider}",
        )


@router.get("/models/available")
async def list_available_models_for_chat(
    current_user: OptionalAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    model_type: str | None = Query(None, alias="type"),
    mode: str | None = Query(
        None,
        description="创作模式：chat→text；image_gen；video（与 type 二选一，type 优先）",
    ),
    provider: str | None = Query(None, min_length=1, max_length=50),
) -> dict[str, Any]:
    """聊天/产品信息模型选择器：系统目录 + personal gateway_models。"""
    _validate_optional_provider(provider)
    effective_type = _effective_model_type_query(model_type=model_type, mode=mode)
    catalog = get_model_catalog_adapter(db)
    user_id, _ = get_owned_user_ids(current_user) if current_user is not None else (None, None)
    return await list_available_models(
        catalog,
        model_type=effective_type,
        user_id=user_id,
        provider=provider,
    )


# =============================================================================
# Models
# =============================================================================


@router.get("/models/presets", response_model=list[GatewayModelPresetResponse])
async def list_model_presets(
    team: CurrentTeam,
    reads: MgmtReads,
    provider: str | None = Query(None, min_length=1, max_length=50),
) -> list[GatewayModelPresetResponse]:
    """返回已同步到 DB 的配置托管全局模型目录；若无则回退 app.toml（兼容旧环境）。"""
    _ = team
    models = await reads.list_gateway_models(team.team_id, only_enabled=True)
    cfg_rows = [
        m
        for m in models
        if m.team_id is None and (m.tags or {}).get(MANAGED_BY_KEY) == MANAGED_CONFIG
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
    return [GatewayModelResponse.model_validate(m) for m in models]


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
            is_platform_admin=team.is_platform_admin,
            enabled=body.enabled,
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
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
            is_platform_admin=team.is_platform_admin,
            fields=body.model_dump(exclude_unset=True, exclude_none=True),
        )
    except ValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
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
        result = await writes.test_gateway_model(model_id, team_id=team.team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return GatewayModelTestResponse.model_validate(result)


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
    model_name = (body.model_name or "").strip() or None
    budget = await writes.upsert_budget(
        scope=body.scope,
        scope_id=body.scope_id,
        period=body.period,
        model_name=model_name,
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
    credential_id: uuid.UUID | None = None,
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
        credential_id=credential_id,
    )
    return RequestLogListResponse(
        items=[RequestLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/{log_id}", response_model=RequestLogDetailResponse)
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
) -> RequestLogDetailResponse:
    try:
        record = await reads.get_request_log(team, log_id, usage_aggregation=usage_aggregation)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Log not found")
    return RequestLogDetailResponse.model_validate(record)


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
        description=("用量切片：workspace=按当前工作区聚合；user=按当前用户跨工作区聚合。"),
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


@router.get("/alerts/events", response_model=list[AlertEventResponse])
async def list_alert_events(
    team: CurrentTeam,
    reads: MgmtReads,
    limit: int = Query(100, ge=1, le=500),
) -> list[AlertEventResponse]:
    rows = await reads.list_alert_events_as_dicts(team.team_id, limit=limit)
    return [AlertEventResponse(**row) for row in rows]


# =============================================================================
# Provider / Entitlement Plans
# =============================================================================


def _provider_plan_to_response(
    plan: ProviderPlan, quotas: list[ProviderPlanQuota]
) -> ProviderPlanResponse:
    return ProviderPlanResponse(
        id=plan.id,
        credential_id=plan.credential_id,
        real_model=plan.real_model,
        label=plan.label,
        valid_from=plan.valid_from,
        valid_until=plan.valid_until,
        is_active=plan.is_active,
        auto_renew=plan.auto_renew,
        notes=plan.notes,
        extra=plan.extra,
        quotas=[PlanQuotaResponse.model_validate(q) for q in quotas],
    )


def _entitlement_plan_to_response(
    plan: EntitlementPlan, quotas: list[EntitlementPlanQuota]
) -> EntitlementPlanResponse:
    return EntitlementPlanResponse(
        id=plan.id,
        scope=plan.scope,
        scope_id=plan.scope_id,
        label=plan.label,
        valid_from=plan.valid_from,
        valid_until=plan.valid_until,
        included_models=list(plan.included_models or []),
        included_capabilities=list(plan.included_capabilities or []),
        is_active=plan.is_active,
        auto_renew=plan.auto_renew,
        notes=plan.notes,
        extra=plan.extra,
        quotas=[EntitlementPlanQuotaResponse.model_validate(q) for q in quotas],
    )


@router.get(
    "/credentials/{credential_id}/provider-plans",
    response_model=list[ProviderPlanResponse],
)
async def list_provider_plans(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> list[ProviderPlanResponse]:
    try:
        await reads.assert_credential_in_team(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_provider_plans_with_quotas_for_credential(credential_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return [_provider_plan_to_response(plan, quotas) for plan, quotas in rows]


@router.post(
    "/credentials/{credential_id}/provider-plans",
    response_model=ProviderPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_plan(
    credential_id: uuid.UUID,
    body: ProviderPlanCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> ProviderPlanResponse:
    try:
        plan = await writes.create_provider_plan(
            credential_id=credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            real_model=body.real_model,
            label=body.label,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            is_active=body.is_active,
            auto_renew=body.auto_renew,
            notes=body.notes,
            extra=body.extra,
            quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
        )
        result = await reads.get_provider_plan_with_quotas(plan.id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan not found after create"
        )
    return _provider_plan_to_response(*result)


@router.patch(
    "/credentials/{credential_id}/provider-plans/{plan_id}",
    response_model=ProviderPlanResponse,
)
async def update_provider_plan(
    credential_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: ProviderPlanUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> ProviderPlanResponse:
    try:
        fields = body.model_dump(exclude_unset=True, exclude_none=True)
        quotas_raw = fields.pop("quotas", None)
        quotas_input = (
            [q if isinstance(q, dict) else q.model_dump(exclude_none=True) for q in quotas_raw]
            if quotas_raw is not None
            else None
        )
        await writes.update_provider_plan(
            plan_id,
            credential_id=credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            fields=fields,
            quotas=quotas_input,
        )
        result = await reads.get_provider_plan_with_quotas(plan_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="provider plan not found")
    return _provider_plan_to_response(*result)


@router.delete(
    "/credentials/{credential_id}/provider-plans/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_provider_plan(
    credential_id: uuid.UUID,
    plan_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_provider_plan(
            plan_id,
            credential_id=credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.get(
    "/credentials/{credential_id}/provider-plan-usage",
    response_model=list[ProviderPlanCostResponse],
)
async def list_provider_plan_usage(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
    days: int = Query(30, ge=1, le=180),
) -> list[ProviderPlanCostResponse]:
    try:
        await reads.assert_credential_in_team(
            credential_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_provider_plans_with_quotas_for_credential(credential_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    out: list[ProviderPlanCostResponse] = []
    for plan, _quotas in rows:
        usage = await reads.get_provider_plan_cost(plan.id, since=start, until=end)
        out.append(
            ProviderPlanCostResponse(
                plan_id=usage.plan_id,
                period_start=usage.period_start,
                period_end=usage.period_end,
                requests=usage.requests,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
            )
        )
    return out


@router.get(
    "/keys/{vkey_id}/entitlements",
    response_model=list[EntitlementPlanResponse],
)
async def list_vkey_entitlements(
    vkey_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> list[EntitlementPlanResponse]:
    try:
        await reads.assert_vkey_in_team(
            vkey_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_entitlement_plans_with_quotas_for_scope("vkey", vkey_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return [_entitlement_plan_to_response(plan, quotas) for plan, quotas in rows]


@router.post(
    "/keys/{vkey_id}/entitlements",
    response_model=EntitlementPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_vkey_entitlement(
    vkey_id: uuid.UUID,
    body: EntitlementPlanCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> EntitlementPlanResponse:
    try:
        plan = await writes.create_entitlement_plan(
            scope="vkey",
            scope_id=vkey_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            label=body.label,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            included_models=body.included_models,
            included_capabilities=body.included_capabilities,
            is_active=body.is_active,
            auto_renew=body.auto_renew,
            notes=body.notes,
            extra=body.extra,
            quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
        )
        result = await reads.get_entitlement_plan_with_quotas(plan.id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan not found")
    return _entitlement_plan_to_response(*result)


@router.patch(
    "/entitlements/{plan_id}",
    response_model=EntitlementPlanResponse,
)
async def update_entitlement_plan(
    plan_id: uuid.UUID,
    body: EntitlementPlanUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> EntitlementPlanResponse:
    try:
        fields = body.model_dump(exclude_unset=True, exclude_none=True)
        quotas_raw = fields.pop("quotas", None)
        quotas_input = (
            [q if isinstance(q, dict) else q.model_dump(exclude_none=True) for q in quotas_raw]
            if quotas_raw is not None
            else None
        )
        await writes.update_entitlement_plan(
            plan_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            fields=fields,
            quotas=quotas_input,
        )
        result = await reads.get_entitlement_plan_with_quotas(plan_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="entitlement plan not found")
    return _entitlement_plan_to_response(*result)


@router.delete(
    "/entitlements/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entitlement_plan(
    plan_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    try:
        await writes.delete_entitlement_plan(
            plan_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc


@router.get(
    "/entitlements/{plan_id}/usage",
    response_model=EntitlementUsageResponse,
)
async def get_entitlement_plan_usage(
    plan_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
    days: int = Query(30, ge=1, le=180),
) -> EntitlementUsageResponse:
    try:
        await reads.assert_entitlement_plan_in_team(
            plan_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    usage = await reads.get_entitlement_usage(plan_id, since=start, until=end)
    return EntitlementUsageResponse(
        plan_id=usage.plan_id,
        period_start=usage.period_start,
        period_end=usage.period_end,
        requests=usage.requests,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=usage.cost_usd,
        charged_usd=usage.charged_usd,
    )


@router.get(
    "/api-key-grants/{grant_id}/entitlements",
    response_model=list[EntitlementPlanResponse],
)
async def list_apikey_grant_entitlements(
    grant_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> list[EntitlementPlanResponse]:
    try:
        await reads.assert_apikey_grant_in_team(
            grant_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
        )
        rows = await reads.list_entitlement_plans_with_quotas_for_scope(
            "apikey_grant", grant_id
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    return [_entitlement_plan_to_response(plan, quotas) for plan, quotas in rows]


@router.post(
    "/api-key-grants/{grant_id}/entitlements",
    response_model=EntitlementPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_apikey_grant_entitlement(
    grant_id: uuid.UUID,
    body: EntitlementPlanCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
    reads: MgmtReads,
) -> EntitlementPlanResponse:
    try:
        plan = await writes.create_entitlement_plan(
            scope="apikey_grant",
            scope_id=grant_id,
            team_id=team.team_id,
            is_platform_admin=team.is_platform_admin,
            label=body.label,
            valid_from=body.valid_from,
            valid_until=body.valid_until,
            included_models=body.included_models,
            included_capabilities=body.included_capabilities,
            is_active=body.is_active,
            auto_renew=body.auto_renew,
            notes=body.notes,
            extra=body.extra,
            quotas=[q.model_dump(exclude_none=True) for q in body.quotas],
        )
        result = await reads.get_entitlement_plan_with_quotas(plan.id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if result is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="plan not found")
    return _entitlement_plan_to_response(*result)


@router.get(
    "/dashboard/margin",
    response_model=MarginSummaryResponse,
)
async def dashboard_margin(
    team: CurrentTeam,
    reads: MgmtReads,
    days: int = Query(30, ge=1, le=365),
    group_by: MarginGroupBy = Query("credential"),
) -> MarginSummaryResponse:
    end = datetime.now(UTC)
    start = end - timedelta(days=days)
    summary = await reads.get_team_margin_summary(
        team.team_id, since=start, until=end, group_by=group_by
    )
    return MarginSummaryResponse(
        period_start=summary.period_start,
        period_end=summary.period_end,
        total_revenue_usd=summary.total_revenue_usd,
        total_cost_usd=summary.total_cost_usd,
        total_margin_usd=summary.total_margin_usd,
        items=[
            MarginGroupItemResponse(
                group_key=i.group_key,
                label=i.label,
                revenue_usd=i.revenue_usd,
                cost_usd=i.cost_usd,
                margin_usd=i.margin_usd,
                margin_ratio=i.margin_ratio,
            )
            for i in summary.items
        ],
    )


__all__ = ["router"]
