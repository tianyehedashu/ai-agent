"""
API Key Router - API Key 管理接口

提供 API Key 的 CRUD 操作和使用日志查询。
"""

import contextlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from bootstrap.config import settings
from domains.identity.application.api_key_use_case import ApiKeyUseCase
from domains.identity.domain.api_key_types import (
    API_KEY_SCOPE_GROUPS,
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ApiKeyScope,
    ApiKeyUpdateRequest,
    ApiKeyUsageLogResponse,
)
from domains.identity.domain.services.api_key_service import ApiKeyGenerator
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.api.deps import DbSession

router = APIRouter()


# =============================================================================
# 依赖注入
# =============================================================================


def _get_api_key_encryption_key() -> str:
    """获取 API Key 加密密钥

    从应用密钥派生 Fernet 加密密钥，用于加密存储完整的 API Key。
    """
    secret = settings.secret_key.get_secret_value()
    return ApiKeyGenerator.derive_encryption_key(secret)


async def get_api_key_service(db: DbSession) -> ApiKeyUseCase:
    """获取 API Key 服务

    Args:
        db: 数据库会话

    Returns:
        ApiKeyUseCase 实例
    """
    encryption_key = _get_api_key_encryption_key()
    return ApiKeyUseCase(db, encryption_key=encryption_key)


# =============================================================================
# 静态路由（必须在动态路由之前定义）
# =============================================================================


@router.get("/scopes/list", response_model=list[str], tags=["API Keys"])
async def list_scopes() -> list[str]:
    """获取可用的 API Key 作用域列表

    Returns:
        作用域列表
    """
    return [s.value for s in ApiKeyScope]


@router.get("/scopes/groups", response_model=dict[str, list[str]], tags=["API Keys"])
async def list_scope_groups() -> dict[str, list[str]]:
    """获取预设的作用域分组

    Returns:
        作用域分组字典
    """
    return {name: [s.value for s in scopes] for name, scopes in API_KEY_SCOPE_GROUPS.items()}


# =============================================================================
# CRUD 路由
# =============================================================================


@router.get("", response_model=list[ApiKeyResponse], tags=["API Keys"])
async def list_api_keys(
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
    include_expired: bool = False,
    include_revoked: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[ApiKeyResponse]:
    """获取当前用户的 API Key 列表

    Args:
        current_user: 当前用户
        service: API Key 服务
        include_expired: 是否包含已过期的 Key
        include_revoked: 是否包含已撤销的 Key
        skip: 跳过记录数
        limit: 返回记录数

    Returns:
        API Key 列表
    """
    entities = await service.list_api_keys(
        user_id=get_user_uuid(current_user),
        include_expired=include_expired,
        include_revoked=include_revoked,
        skip=skip,
        limit=limit,
    )
    return [ApiKeyResponse.from_entity(e) for e in entities]


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["API Keys"],
)
async def create_api_key(
    request: ApiKeyCreateRequest,
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
) -> ApiKeyCreatedResponse:
    """创建新的 API Key

    注意：完整密钥仅在创建时返回一次，请妥善保存。

    Args:
        request: 创建请求
        current_user: 当前用户
        service: API Key 服务

    Returns:
        创建的 API Key 和完整密钥
    """
    entity, plain_key = await service.create_api_key(
        user_id=get_user_uuid(current_user),
        request=request,
    )

    return ApiKeyCreatedResponse(
        api_key=ApiKeyResponse.from_entity(entity),
        plain_key=plain_key,
    )


@router.get("/{api_key_id}", response_model=ApiKeyResponse, tags=["API Keys"])
async def get_api_key(
    api_key_id: str,
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
) -> ApiKeyResponse:
    """获取 API Key 详情

    Args:
        api_key_id: API Key ID
        current_user: 当前用户
        service: API Key 服务

    Returns:
        API Key 详情

    Raises:
        HTTPException: API Key 不存在或无权限访问
    """
    try:
        entity = await service.get_api_key(
            api_key_id=uuid.UUID(api_key_id),
            user_id=get_user_uuid(current_user),
        )
        return ApiKeyResponse.from_entity(entity)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found",
            ) from e
        raise


@router.get(
    "/{api_key_id}/reveal",
    response_model=dict[str, str],
    tags=["API Keys"],
)
async def reveal_api_key(
    api_key_id: str,
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
) -> dict[str, str]:
    """解密并显示完整的 API Key

    仅在配置了加密密钥的情况下可用，且仅对已加密的新密钥有效。

    Args:
        api_key_id: API Key ID
        current_user: 当前用户
        service: API Key 服务

    Returns:
        包含完整 API Key 的字典

    Raises:
        HTTPException: API Key 不存在、无权限访问或无法解密
    """
    try:
        plain_key = await service.reveal_api_key(
            api_key_id=uuid.UUID(api_key_id),
            user_id=get_user_uuid(current_user),
        )
        return {"api_key": plain_key}
    except Exception as e:
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found",
            ) from e
        if "validation" in error_msg or "decrypt" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        raise


@router.put("/{api_key_id}", response_model=ApiKeyResponse, tags=["API Keys"])
async def update_api_key(
    api_key_id: str,
    request: ApiKeyUpdateRequest,
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
) -> ApiKeyResponse:
    """更新 API Key

    支持更新名称、描述、作用域和延长过期时间。

    Args:
        api_key_id: API Key ID
        request: 更新请求
        current_user: 当前用户
        service: API Key 服务

    Returns:
        更新后的 API Key

    Raises:
        HTTPException: API Key 不存在或无权限访问
    """
    try:
        entity = await service.update_api_key(
            api_key_id=uuid.UUID(api_key_id),
            user_id=get_user_uuid(current_user),
            request=request,
        )
        return ApiKeyResponse.from_entity(entity)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API Key not found",
            ) from e
        if "validation" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        raise


@router.post(
    "/{api_key_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["API Keys"],
)
async def revoke_api_key(
    api_key_id: str,
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
) -> None:
    """撤销 API Key

    Args:
        api_key_id: API Key ID
        current_user: 当前用户
        service: API Key 服务

    Raises:
        HTTPException: API Key 不存在或无权限访问
    """
    with contextlib.suppress(Exception):
        await service.revoke_api_key(
            api_key_id=uuid.UUID(api_key_id),
            user_id=get_user_uuid(current_user),
        )


@router.delete(
    "/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["API Keys"],
)
async def delete_api_key(
    api_key_id: str,
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
) -> None:
    """删除 API Key

    Args:
        api_key_id: API Key ID
        current_user: 当前用户
        service: API Key 服务

    Raises:
        HTTPException: API Key 不存在或无权限访问
    """
    with contextlib.suppress(Exception):
        await service.delete_api_key(
            api_key_id=uuid.UUID(api_key_id),
            user_id=get_user_uuid(current_user),
        )


@router.get("/{api_key_id}/logs", response_model=list[ApiKeyUsageLogResponse], tags=["API Keys"])
async def get_api_key_logs(
    api_key_id: str,
    current_user: RequiredAuthUser,
    service: ApiKeyUseCase = Depends(get_api_key_service),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[ApiKeyUsageLogResponse]:
    """获取 API Key 使用日志

    Args:
        api_key_id: API Key ID
        current_user: 当前用户
        service: API Key 服务
        skip: 跳过记录数
        limit: 返回记录数

    Returns:
        使用日志列表
    """
    logs, _ = await service.get_usage_logs(
        api_key_id=uuid.UUID(api_key_id),
        user_id=get_user_uuid(current_user),
        skip=skip,
        limit=limit,
    )
    return logs
