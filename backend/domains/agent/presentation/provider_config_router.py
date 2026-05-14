"""
Provider Config Router - 用户 LLM 提供商配置 API

提供用户大模型提供商 Key 的 CRUD 与测试接口。
与 Gateway ``provider_credentials``（user scope）双写，列表优先读统一凭据表。
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from bootstrap.config import settings
from domains.agent.application.llm_key_service import EncryptorProtocol
from domains.agent.infrastructure.provider_config_encryptor import get_provider_config_encryptor
from domains.agent.infrastructure.repositories.user_provider_config_repository import (
    UserProviderConfigRepository,
)
from domains.gateway.application.management import (
    GatewayManagementReadService,
    GatewayManagementWriteService,
)
from domains.gateway.domain.errors import CredentialInUseError
from domains.gateway.domain.types import USER_GATEWAY_CREDENTIAL_PROVIDERS
from domains.identity.presentation.deps import RequiredAuthUser, get_user_uuid
from libs.api.deps import DbSession
from libs.crypto import decrypt_value, derive_encryption_key, encrypt_value

router = APIRouter()

# 与 ``USER_GATEWAY_CREDENTIAL_PROVIDERS`` 同源；保留别名供本模块与外部引用
SUPPORTED_PROVIDERS = USER_GATEWAY_CREDENTIAL_PROVIDERS


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
    name: str = Field(default="default", description="凭据别名；旧版单条语义为 default")
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


def get_gateway_management_reads(db: DbSession) -> GatewayManagementReadService:
    return GatewayManagementReadService(db)


def get_gateway_management_writes(db: DbSession) -> GatewayManagementWriteService:
    return GatewayManagementWriteService(db)


def _gateway_encryption_key() -> str:
    return derive_encryption_key(settings.secret_key.get_secret_value())


def _validate_provider(provider: str) -> str:
    """校验提供商名称"""
    p = provider.lower()
    if p not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"不支持的提供商: {provider}。支持: {', '.join(sorted(SUPPORTED_PROVIDERS))}",
        )
    return p


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
    reads: GatewayManagementReadService = Depends(get_gateway_management_reads),
) -> list[ProviderConfigResponse]:
    """列出当前用户的提供商配置（优先 provider_credentials）"""
    user_id = get_user_uuid(current_user)
    creds = await reads.list_user_credentials(user_id)
    if creds:
        return [
            ProviderConfigResponse(
                id=c.id,
                provider=c.provider,
                name=c.name,
                api_base=c.api_base,
                is_active=c.is_active,
            )
            for c in creds
        ]
    configs = await repo.list_by_user(user_id)
    return [
        ProviderConfigResponse(
            id=c.id,
            provider=c.provider,
            name="default",
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
    writes: GatewayManagementWriteService = Depends(get_gateway_management_writes),
    encryptor: EncryptorProtocol = Depends(get_provider_config_encryptor),
) -> ProviderConfigResponse:
    """创建或更新指定提供商的配置（双写到 user_provider_configs 与 provider_credentials）"""
    provider_lower = _validate_provider(provider)

    user_id = get_user_uuid(current_user)
    encrypted_legacy = encryptor.encrypt(body.api_key)
    encrypted_gw = encrypt_value(body.api_key, _gateway_encryption_key())

    await repo.upsert(
        user_id=user_id,
        provider=provider_lower,
        api_key=encrypted_legacy,
        api_base=body.api_base,
        is_active=body.is_active,
    )
    sync_row = await writes.sync_user_provider_legacy_row(
        actor_user_id=user_id,
        provider=provider_lower,
        api_key_encrypted=encrypted_gw,
        api_base=body.api_base,
        is_active=body.is_active,
    )
    return ProviderConfigResponse(
        id=sync_row.id,
        provider=sync_row.provider,
        name=sync_row.name,
        api_base=sync_row.api_base,
        is_active=sync_row.is_active,
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
    reads: GatewayManagementReadService = Depends(get_gateway_management_reads),
    writes: GatewayManagementWriteService = Depends(get_gateway_management_writes),
) -> None:
    """删除指定提供商下全部 user 凭据行，并删除旧版 user_provider_configs 行"""
    provider_lower = _validate_provider(provider)

    user_id = get_user_uuid(current_user)
    legacy = await repo.get_by_user_and_provider(user_id, provider_lower)
    creds = await reads.list_user_credentials(user_id)
    has_pc = any(c.provider == provider_lower for c in creds)
    if legacy is None and not has_pc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"未找到提供商 {provider} 的配置",
        )
    try:
        if has_pc:
            await writes.delete_all_user_credentials_for_provider(
                actor_user_id=user_id, provider=provider_lower
            )
    except CredentialInUseError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if legacy is not None:
        await repo.delete(user_id, provider_lower)


def test_provider_connection(provider: str, api_key: str, api_base: str | None = None) -> bool:
    """测试提供商 Key 是否有效（可被测试 mock）

    实际实现可调用 LiteLLM 或各提供商 API 做一次轻量请求。
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
    reads: GatewayManagementReadService = Depends(get_gateway_management_reads),
    encryptor: EncryptorProtocol = Depends(get_provider_config_encryptor),
) -> ProviderTestResponse:
    """测试指定提供商的 Key 是否有效"""
    provider_lower = _validate_provider(provider)

    user_id = get_user_uuid(current_user)
    creds = await reads.list_user_credentials(user_id)
    plain_key: str | None = None
    api_base: str | None = None
    for c in creds:
        if c.provider != provider_lower:
            continue
        if c.name in ("default", provider_lower):
            plain_key = decrypt_value(c.api_key_encrypted, _gateway_encryption_key())
            api_base = c.api_base
            break
    if plain_key is None:
        for c in creds:
            if c.provider == provider_lower:
                plain_key = decrypt_value(c.api_key_encrypted, _gateway_encryption_key())
                api_base = c.api_base
                break
    if plain_key is None:
        config = await repo.get_by_user_and_provider(user_id, provider_lower)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到提供商 {provider} 的配置，请先保存 Key",
            )
        plain_key = encryptor.decrypt(config.api_key)
        api_base = config.api_base

    success = test_provider_connection(provider_lower, plain_key, api_base)
    return ProviderTestResponse(success=success)
