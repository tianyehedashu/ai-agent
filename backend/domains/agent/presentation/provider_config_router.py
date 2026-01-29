"""
Provider Config Router - 用户 LLM 提供商配置 API

提供用户大模型提供商 Key 的 CRUD 与测试接口。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from domains.agent.application.llm_key_service import EncryptorProtocol
from domains.agent.infrastructure.provider_config_encryptor import get_provider_config_encryptor
from domains.agent.infrastructure.repositories.user_provider_config_repository import (
    UserProviderConfigRepository,
)
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.api.deps import DbSession

router = APIRouter()

# 支持的提供商（与 plan 一致）
SUPPORTED_PROVIDERS = frozenset(
    {"openai", "anthropic", "dashscope", "zhipuai", "deepseek", "volcengine"}
)


# =============================================================================
# Schemas
# =============================================================================


class ProviderConfigUpdateRequest(BaseModel):
    """提供商配置更新请求"""

    api_key: str = Field(..., min_length=1, description="API Key（明文，存储时加密）")
    api_base: str | None = Field(None, max_length=255, description="自定义 API Base URL")
    is_active: bool = True


class ProviderConfigResponse(BaseModel):
    """提供商配置响应（不包含 api_key 明文）"""

    id: uuid.UUID
    provider: str
    api_base: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class ProviderTestResponse(BaseModel):
    """测试 Key 有效性响应"""

    success: bool


# =============================================================================
# Dependencies
# =============================================================================


def get_provider_config_repo(db: DbSession) -> UserProviderConfigRepository:
    """获取用户提供商配置仓储"""
    return UserProviderConfigRepository(db)


def _validate_provider(provider: str) -> None:
    """校验提供商名称"""
    if provider.lower() not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"不支持的提供商: {provider}。支持: {', '.join(sorted(SUPPORTED_PROVIDERS))}",
        )


# =============================================================================
# Routes
# =============================================================================


@router.get(
    "",
    response_model=list[ProviderConfigResponse],
    tags=["Settings - Provider Config"],
)
async def list_provider_configs(
    current_user: RequiredAuthUser,
    repo: UserProviderConfigRepository = Depends(get_provider_config_repo),
) -> list[ProviderConfigResponse]:
    """列出当前用户的提供商配置"""
    user_id = get_user_uuid(current_user)
    configs = await repo.list_by_user(user_id)
    return [
        ProviderConfigResponse(
            id=c.id,
            provider=c.provider,
            api_base=c.api_base,
            is_active=c.is_active,
        )
        for c in configs
    ]


@router.put(
    "/{provider}",
    response_model=ProviderConfigResponse,
    tags=["Settings - Provider Config"],
)
async def update_provider_config(
    provider: str,
    body: ProviderConfigUpdateRequest,
    current_user: RequiredAuthUser,
    repo: UserProviderConfigRepository = Depends(get_provider_config_repo),
    encryptor: EncryptorProtocol = Depends(get_provider_config_encryptor),
) -> ProviderConfigResponse:
    """创建或更新指定提供商的配置"""
    provider_lower = provider.lower()
    _validate_provider(provider_lower)

    user_id = get_user_uuid(current_user)
    encrypted_key = encryptor.encrypt(body.api_key)

    config = await repo.upsert(
        user_id=user_id,
        provider=provider_lower,
        api_key=encrypted_key,
        api_base=body.api_base,
        is_active=body.is_active,
    )
    return ProviderConfigResponse(
        id=config.id,
        provider=config.provider,
        api_base=config.api_base,
        is_active=config.is_active,
    )


@router.delete(
    "/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Settings - Provider Config"],
)
async def delete_provider_config(
    provider: str,
    current_user: RequiredAuthUser,
    repo: UserProviderConfigRepository = Depends(get_provider_config_repo),
) -> None:
    """删除指定提供商的配置"""
    provider_lower = provider.lower()
    _validate_provider(provider_lower)

    user_id = get_user_uuid(current_user)
    deleted = await repo.delete(user_id, provider_lower)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到提供商 {provider} 的配置",
        )


def test_provider_connection(provider: str, api_key: str, api_base: str | None = None) -> bool:
    """测试提供商 Key 是否有效（可被测试 mock）

    实际实现可调用各提供商的最小 API（如 models list 或简单 completion）。
    集成测试中会 mock 此函数。
    """
    # 占位：实际可调用 LiteLLM 或各提供商 API 做一次轻量请求
    _ = provider
    _ = api_key
    _ = api_base
    return True


@router.post(
    "/{provider}/test",
    response_model=ProviderTestResponse,
    tags=["Settings - Provider Config"],
)
async def test_provider_config(
    provider: str,
    current_user: RequiredAuthUser,
    repo: UserProviderConfigRepository = Depends(get_provider_config_repo),
    encryptor: EncryptorProtocol = Depends(get_provider_config_encryptor),
) -> ProviderTestResponse:
    """测试指定提供商的 Key 是否有效"""
    provider_lower = provider.lower()
    _validate_provider(provider_lower)

    user_id = get_user_uuid(current_user)
    config = await repo.get_by_user_and_provider(user_id, provider_lower)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到提供商 {provider} 的配置，请先保存 Key",
        )

    plain_key = encryptor.decrypt(config.api_key)
    success = test_provider_connection(provider_lower, plain_key, config.api_base)
    return ProviderTestResponse(success=success)
