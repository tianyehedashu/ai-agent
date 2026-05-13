"""
User Model Router - 用户模型管理 API

提供用户自定义模型的 CRUD、连接测试、可用模型列表（系统 + 用户合并）。
"""

from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from domains.agent.application.user_model_use_case import UserModelUseCase
from domains.identity.presentation.deps import AuthUser, OptionalAuthUser, get_owned_user_ids
from libs.api.deps import get_user_model_service
from libs.exceptions import NotFoundError, ValidationError

router = APIRouter()


# =============================================================================
# Request / Response Schemas
# =============================================================================


class CreateUserModelBody(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=200)
    api_key: str | None = None
    api_base: str | None = None
    model_types: list[str] = Field(default_factory=lambda: ["text"])
    config: dict[str, Any] | None = None


class UpdateUserModelBody(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    provider: str | None = Field(None, min_length=1, max_length=50)
    model_id: str | None = Field(None, min_length=1, max_length=200)
    api_key: str | None = None
    api_base: str | None = None
    model_types: list[str] | None = None
    config: dict[str, Any] | None = None
    is_active: bool | None = None


# =============================================================================
# CRUD
# =============================================================================


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_model(
    body: CreateUserModelBody,
    current_user: AuthUser,
    service: UserModelUseCase = Depends(get_user_model_service),
) -> dict[str, Any]:
    """创建用户模型"""
    user_id, anonymous_user_id = get_owned_user_ids(current_user)
    try:
        return await service.create(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            display_name=body.display_name,
            provider=body.provider,
            model_id=body.model_id,
            api_key=body.api_key,
            api_base=body.api_base,
            model_types=body.model_types,
            config=body.config,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/")
async def list_models(
    current_user: AuthUser,
    service: UserModelUseCase = Depends(get_user_model_service),
    model_type: str | None = Query(None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    """列出当前用户的模型"""
    items, total = await service.list_models(
        model_type=model_type,
        skip=skip,
        limit=limit,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/available")
async def list_available_models(
    current_user: OptionalAuthUser,
    service: UserModelUseCase = Depends(get_user_model_service),
    model_type: str | None = Query(None, alias="type"),
) -> dict[str, Any]:
    """可用模型列表（系统模型 + 用户模型合并）

    无认证时仅返回系统模型，不抛 401，便于产品信息等场景展示模型选择器。
    返回 default_for_text / default_for_vision 供前端展示「默认（模型名）」。
    """
    system_models = service.get_available_models(model_type=model_type)
    default_for_text = service.get_default_for_type("text")
    default_for_vision = service.get_default_for_type("image")
    default_for_image_gen = service.get_default_for_type("image_gen")
    if current_user is None:
        return {
            "system_models": system_models,
            "user_models": [],
            "default_for_text": default_for_text,
            "default_for_vision": default_for_vision,
            "default_for_image_gen": default_for_image_gen,
        }
    user_items, _ = await service.list_models(model_type=model_type, limit=100)
    return {
        "system_models": system_models,
        "user_models": user_items,
        "default_for_text": default_for_text,
        "default_for_vision": default_for_vision,
        "default_for_image_gen": default_for_image_gen,
    }


@router.get("/{model_uuid}")
async def get_model(
    model_uuid: uuid.UUID,
    current_user: AuthUser,
    service: UserModelUseCase = Depends(get_user_model_service),
) -> dict[str, Any]:
    """模型详情"""
    try:
        return await service.get_model(model_uuid)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{model_uuid}")
async def update_model(
    model_uuid: uuid.UUID,
    body: UpdateUserModelBody,
    current_user: AuthUser,
    service: UserModelUseCase = Depends(get_user_model_service),
) -> dict[str, Any]:
    """更新模型"""
    update_data = body.model_dump(exclude_unset=True)
    try:
        return await service.update(model_uuid, **update_data)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{model_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_uuid: uuid.UUID,
    current_user: AuthUser,
    service: UserModelUseCase = Depends(get_user_model_service),
) -> None:
    """删除模型"""
    try:
        await service.delete(model_uuid)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{model_uuid}/test")
async def test_model_connection(
    model_uuid: uuid.UUID,
    current_user: AuthUser,
    service: UserModelUseCase = Depends(get_user_model_service),
) -> dict[str, Any]:
    """测试模型连接"""
    try:
        return await service.test_connection(model_uuid)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
