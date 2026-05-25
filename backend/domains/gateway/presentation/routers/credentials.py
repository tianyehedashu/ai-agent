"""Team-scope Credentials 子 router。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from domains.gateway.presentation.credential_response import (
    build_credential_response,
    build_credential_summary_response,
    decrypt_credential_api_key_for_reveal,
)
from domains.gateway.presentation.deps import (
    CurrentTeam,
    RequiredTeamAdmin,
)
from domains.gateway.presentation.schemas.common import (
    CredentialResponse,
    CredentialSummaryResponse,
    CredentialUpdate,
    ManagedCredentialCreate,
)
from domains.gateway.presentation.schemas.credential_upstream_catalog import (
    BatchImportFailureItem,
    CredentialProbeResponse,
    TeamGatewayModelBatchImportCreatedItem,
    TeamGatewayModelBatchImportRequest,
    TeamGatewayModelBatchImportResponse,
)
from libs.crypto import encrypt_value
from libs.exceptions import AuthenticationError, ValidationError

from ._common import (
    CatalogSvc,
    MgmtReads,
    MgmtWrites,
    credential_probe_to_response,
    encryption_key,
    validate_managed_credential_provider,
)

router = APIRouter()


@router.get("/credentials", response_model=list[CredentialResponse])
async def list_credentials(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[CredentialResponse]:
    creds = await reads.list_credentials_for_team(
        team.team_id,
        include_system=team.is_platform_admin,
        encryption_key=encryption_key(),
    )
    return [build_credential_response(c, encryption_key=encryption_key()) for c in creds]


@router.get("/credentials/summaries", response_model=list[CredentialSummaryResponse])
async def list_credential_summaries(
    team: CurrentTeam,
    reads: MgmtReads,
) -> list[CredentialSummaryResponse]:
    """团队 member 可读：解析模型 credential_id → 显示名（含 system，无密钥）。"""
    rows = await reads.list_credential_summaries_for_team(
        team.team_id,
        user_id=team.user_id,
        is_platform_admin=team.is_platform_admin,
    )
    return [build_credential_summary_response(r) for r in rows]


@router.get("/credentials/{credential_id}", response_model=CredentialResponse)
async def get_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> CredentialResponse:
    row = await reads.get_managed_credential_for_team(
        credential_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )
    return build_credential_response(row, encryption_key=encryption_key())


@router.get("/credentials/{credential_id}/reveal", response_model=dict[str, str])
async def reveal_managed_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    reads: MgmtReads,
) -> dict[str, str]:
    """解密并返回完整 API Key（与 GET 凭据详情相同权限；用于前端显式展示）。"""
    row = await reads.get_managed_credential_for_team(
        credential_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )
    plain = decrypt_credential_api_key_for_reveal(
        row,
        encryption_key=encryption_key(),
    )
    return {"api_key": plain}


@router.post("/credentials", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: ManagedCredentialCreate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> CredentialResponse:
    provider = validate_managed_credential_provider(body.provider)
    encrypted = encrypt_value(body.api_key, encryption_key())
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
            tenant_id=team.team_id,
            provider=provider,
            name=body.name,
            api_key_encrypted=encrypted,
            api_base=body.api_base,
            extra=body.extra,
        )
    return build_credential_response(cred, encryption_key=encryption_key())


@router.patch("/credentials/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> CredentialResponse:
    encrypted = encrypt_value(body.api_key, encryption_key()) if body.api_key else None
    updated = await writes.update_managed_credential(
        credential_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
        api_key_encrypted=encrypted,
        api_base=body.api_base,
        extra=body.extra,
        is_active=body.is_active,
        name=body.name,
    )
    return build_credential_response(updated, encryption_key=encryption_key())


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> None:
    await writes.delete_managed_credential(
        credential_id,
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
    )


@router.post("/credentials/{credential_id}/probe", response_model=CredentialProbeResponse)
async def probe_managed_credential_endpoint(
    credential_id: uuid.UUID,
    team: RequiredTeamAdmin,
    catalog: CatalogSvc,
) -> CredentialProbeResponse:
    """POST 触发上游 OpenAI 兼容 ``/v1/models`` 列举（同路径重复调用即刷新）。"""
    result = await catalog.probe_managed_credential(
        tenant_id=team.team_id,
        is_platform_admin=team.is_platform_admin,
        credential_id=credential_id,
    )
    return credential_probe_to_response(result)


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
    tuples = [(it.upstream_model_id, it.name) for it in body.items]
    created_raw, failed_raw = await catalog.batch_import_team_models(
        tenant_id=team.team_id,
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
        raise ValidationError("credential_id required")
    new_cred = await writes.import_user_credential_to_team(
        user_credential_id=user_credential_id,
        tenant_id=team.team_id,
        actor_user_id=team.user_id,
        is_platform_admin=team.is_platform_admin,
    )
    return build_credential_response(new_cred, encryption_key=encryption_key())


@router.post("/credentials/import")
async def import_all_user_credentials(
    team: RequiredTeamAdmin,
    writes: MgmtWrites,
) -> dict[str, int]:
    """一键把当前用户的所有 user-scope 凭据导入到当前团队（只复制不删除原凭据）"""
    if team.user_id is None:
        raise AuthenticationError("User context required")
    created = await writes.import_all_user_credentials_to_team(
        actor_user_id=team.user_id,
        tenant_id=team.team_id,
    )
    return {"created": created}


__all__ = ["router"]
