"""User-scoped Personal Models 子 router (含 /models/available)。"""

from __future__ import annotations

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.model_list_pipeline import resolved_registry_ability
from domains.gateway.application.model_selector_list_reads import list_available_models_page
from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter
from domains.gateway.presentation.gateway_model_list_response import (
    build_personal_model_list_response,
)
from domains.gateway.presentation.model_list_query import ModelListQueryDep
from domains.gateway.presentation.schemas.common import (
    AvailableModelsListResponse,
    GatewayModelBatchDeleteFailureItem,
    GatewayModelBatchDeleteRequest,
    GatewayModelBatchDeleteResponse,
    GatewayModelTestResponse,
    ModelConnectivitySummary,
    PaginatedSelectorModels,
    PersonalModelCreate,
    PersonalModelListResponse,
    PersonalModelResponse,
    PersonalModelUpdate,
)
from domains.identity.presentation.deps import (
    OptionalAuthUser,
    RequiredAuthUser,
    get_user_uuid,
)
from libs.db.database import get_db
from libs.exceptions import NotFoundError

from ._common import (
    MgmtReads,
    MgmtWrites,
    effective_model_type_query,
    validate_optional_provider,
    validate_personal_model_provider,
)

router = APIRouter()


@router.get("/my-models", response_model=PersonalModelListResponse)
async def list_my_models(
    current_user: RequiredAuthUser,
    reads: MgmtReads,
    query: ModelListQueryDep,
) -> PersonalModelListResponse:
    user_id = get_user_uuid(current_user)
    page = await reads.list_personal_gateway_models_page(user_id, query)
    return build_personal_model_list_response(page)


@router.get("/my-models/{model_id}", response_model=PersonalModelResponse)
async def get_my_model(
    model_id: uuid.UUID,
    current_user: RequiredAuthUser,
    reads: MgmtReads,
) -> PersonalModelResponse:
    user_id = get_user_uuid(current_user)
    row = await reads.get_personal_gateway_model(user_id, model_id)
    if row is None:
        raise NotFoundError("Model")
    return PersonalModelResponse.from_gateway_model(row)


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
    rows = await writes.create_personal_models(
        user_id,
        display_name=body.display_name.strip(),
        provider=provider,
        model_id=body.model_id.strip(),
        credential_id=body.credential_id,
        model_types=body.model_types,
        tags=body.tags,
    )
    return [PersonalModelResponse.from_gateway_model(r) for r in rows]


@router.patch("/my-models/{model_id}", response_model=PersonalModelResponse)
async def update_my_model(
    model_id: uuid.UUID,
    body: PersonalModelUpdate,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> PersonalModelResponse:
    user_id = get_user_uuid(current_user)
    updated = await writes.update_personal_model(
        user_id,
        model_id,
        fields=body.model_dump(exclude_unset=True, exclude_none=True),
    )
    return PersonalModelResponse.from_gateway_model(updated)


@router.delete("/my-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_model(
    model_id: uuid.UUID,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> None:
    user_id = get_user_uuid(current_user)
    await writes.delete_personal_model(user_id, model_id)


@router.post("/my-models/batch-delete", response_model=GatewayModelBatchDeleteResponse)
async def batch_delete_my_models(
    payload: GatewayModelBatchDeleteRequest,
    current_user: RequiredAuthUser,
    writes: MgmtWrites,
) -> GatewayModelBatchDeleteResponse:
    user_id = get_user_uuid(current_user)
    result = await writes.delete_personal_models_batch(user_id, payload.model_ids)
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
    result = await writes.test_personal_model(user_id, model_id)
    return GatewayModelTestResponse.model_validate(result)


@router.get("/models/available", response_model=AvailableModelsListResponse)
async def list_available_models_for_chat(
    current_user: OptionalAuthUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    query: ModelListQueryDep,
    model_type: str | None = Query(None, alias="type"),
    mode: str | None = Query(
        None,
        description="创作模式：chat→text；image_gen；video（与 type 二选一，type 优先）",
    ),
) -> AvailableModelsListResponse:
    """聊天/产品信息模型选择器：系统目录 + personal gateway_models（分页）。"""
    validate_optional_provider(query.provider)
    effective_type = effective_model_type_query(model_type=model_type, mode=mode)
    if effective_type is None:
        effective_type = resolved_registry_ability(query)
    catalog = get_model_catalog_adapter(db)
    user_id: uuid.UUID | None = None
    if current_user is not None and not current_user.is_anonymous:
        user_id = uuid.UUID(current_user.id)
    raw = await list_available_models_page(
        catalog,
        db,
        query,
        model_type=effective_type,
        user_id=user_id,
    )
    summary = raw.get("connectivity_summary")
    return AvailableModelsListResponse(
        system_models=PaginatedSelectorModels.model_validate(raw["system_models"]),
        user_models=PaginatedSelectorModels.model_validate(raw["user_models"]),
        default_for_text=raw.get("default_for_text"),
        default_for_vision=raw.get("default_for_vision"),
        default_for_image_gen=raw.get("default_for_image_gen"),
        connectivity_summary=(
            ModelConnectivitySummary.model_validate(summary) if summary is not None else None
        ),
    )


__all__ = ["router"]
