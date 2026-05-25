"""User-scoped Credentials 子 router (JWT only; 不要求 X-Team-Id)。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from domains.gateway.presentation.credential_response import (
    build_credential_response,
    decrypt_credential_api_key_for_reveal,
)
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    CredentialResponse,
    CredentialUpdate,
    UserCredentialCreate,
)
from domains.gateway.presentation.schemas.credential_upstream_catalog import (
    BatchImportFailureItem,
    CredentialProbeResponse,
    PersonalModelBatchImportCreatedItem,
    PersonalModelBatchImportRequest,
    PersonalModelBatchImportResponse,
)
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.crypto import encrypt_value
from libs.exceptions import HttpMappableDomainError

from ._common import (
    CatalogSvc,
    MgmtReads,
    MgmtWrites,
    credential_probe_to_response,
    encryption_key,
    validate_personal_model_provider,
    validate_user_credential_provider,
)

router = APIRouter()


@router.get("/my-credentials", response_model=list[CredentialResponse])
async def list_my_credentials(
    current_user: RequiredAuthUser,
    reads: MgmtReads,
) -> list[CredentialResponse]:
    user_id = get_user_uuid(current_user)
    creds = await reads.list_user_credentials(user_id, encryption_key=encryption_key())
    return [build_credential_response(c, encryption_key=encryption_key()) for c in creds]


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
            encryption_key=encryption_key(),
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
    provider = validate_user_credential_provider(body.provider)
    encrypted = encrypt_value(body.api_key, encryption_key())
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
    return build_credential_response(cred, encryption_key=encryption_key())


@router.patch("/my-credentials/{credential_id}", response_model=CredentialResponse)
async def update_my_credential(
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> CredentialResponse:
    user_id = get_user_uuid(current_user)
    try:
        encrypted = encrypt_value(body.api_key, encryption_key()) if body.api_key else None
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
    return build_credential_response(updated, encryption_key=encryption_key())


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
    return credential_probe_to_response(result)


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
    provider = validate_personal_model_provider(body.provider)
    if body.items:
        import_items = [
            (item.upstream_model_id, tuple(item.model_types)) for item in body.items
        ]
        legacy_ids: list[str] | None = None
        legacy_types: list[str] | None = None
    else:
        import_items = []
        legacy_ids = body.upstream_model_ids
        legacy_types = body.model_types
    try:
        created_raw, failed_raw = await catalog.batch_import_personal_models(
            user_id=user_id,
            credential_id=credential_id,
            provider=provider,
            import_items=import_items,
            upstream_model_ids=legacy_ids,
            model_types=legacy_types,
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


__all__ = ["router"]
