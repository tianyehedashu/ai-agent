"""User-scoped Personal Models 子 router (含 /models/available)。"""

from __future__ import annotations

from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.model_selector_reads import list_available_models
from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    GatewayModelBatchDeleteFailureItem,
    GatewayModelBatchDeleteRequest,
    GatewayModelBatchDeleteResponse,
    GatewayModelTestResponse,
    PersonalModelCreate,
    PersonalModelResponse,
    PersonalModelUpdate,
)
from domains.identity.presentation.deps import (
    OptionalAuthUser,
    RequiredAuthUser,
    get_user_uuid,
)
from libs.db.database import get_db
from libs.exceptions import HttpMappableDomainError, ValidationError

from ._common import (
    MgmtReads,
    MgmtWrites,
    effective_model_type_query,
    validate_optional_provider,
    validate_personal_model_provider,
)

router = APIRouter()


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
    provider = validate_personal_model_provider(body.provider)
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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
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


@router.post("/my-models/batch-delete", response_model=GatewayModelBatchDeleteResponse)
async def batch_delete_my_models(
    payload: GatewayModelBatchDeleteRequest,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> GatewayModelBatchDeleteResponse:
    user_id = get_user_uuid(current_user)
    try:
        result = await writes.delete_personal_models_batch(user_id, payload.model_ids)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
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
    validate_optional_provider(provider)
    effective_type = effective_model_type_query(model_type=model_type, mode=mode)
    catalog = get_model_catalog_adapter(db)
    user_id: uuid.UUID | None = None
    if current_user is not None and not current_user.is_anonymous:
        user_id = uuid.UUID(current_user.id)
    return await list_available_models(
        catalog,
        model_type=effective_type,
        user_id=user_id,
        provider=provider,
    )


__all__ = ["router"]
