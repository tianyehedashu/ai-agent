"""Gateway management 子 router 共享 deps、Annotated 类型与 helper 函数。

抽取自 ``management_router.py`` 第 1–260 行；各子 router 模块经此导入避免重复。

约定：

- ``MgmtReads`` / ``MgmtWrites`` / ``CatalogSvc`` 等 ``Annotated`` 别名给子 router 装配 ``Depends`` 用。
- 跨 router 共享的 helper（``vkey_to_response``、``credential_probe_to_response``、
  ``validate_*_provider``、``encryption_key`` 等）走"无前导下划线"对外公开；
- 仅本模块内部消费的 ``Depends`` 工厂保留 ``_`` 前缀，避免泄漏到子 router。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.gateway.application.management import (
    GatewayManagementReadService,
    GatewayManagementWriteService,
)
from domains.gateway.application.management.credential_upstream_catalog import (
    CredentialUpstreamCatalogService,
)
from domains.gateway.domain.credential_probe import CredentialProbeResult
from domains.gateway.domain.types import (
    MANAGED_GATEWAY_CREDENTIAL_PROVIDERS,
    PERSONAL_MODEL_PROVIDERS,
    USER_GATEWAY_CREDENTIAL_PROVIDERS,
)
from domains.gateway.presentation.schemas.common import (
    VirtualKeyResponse,
)
from domains.gateway.presentation.schemas.credential_upstream_catalog import (
    CredentialProbeResponse,
    UpstreamModelItemResponse,
)
from libs.crypto import derive_encryption_key
from libs.db.database import get_db

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey


def credential_probe_to_response(result: CredentialProbeResult) -> CredentialProbeResponse:
    return CredentialProbeResponse(
        credential_id=result.credential_id,
        probe_at=result.probe_at,
        support=result.support,
        upstream=result.upstream,
        items=[
            UpstreamModelItemResponse(
                id=i.id,
                owned_by=i.owned_by,
                already_registered=i.already_registered,
                registered_names=list(i.registered_names),
            )
            for i in result.items
        ],
        message=result.message,
        http_status=result.http_status,
    )


def validate_user_credential_provider(provider: str) -> str:
    p = provider.lower()
    if p not in USER_GATEWAY_CREDENTIAL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"不支持的提供商: {provider}。"
                f"支持: {', '.join(sorted(USER_GATEWAY_CREDENTIAL_PROVIDERS))}"
            ),
        )
    return p


def validate_managed_credential_provider(provider: str) -> str:
    """校验 team/system 凭据 provider；与前端 `provider-schemas.ts` 表对齐。"""
    p = provider.lower()
    if p not in MANAGED_GATEWAY_CREDENTIAL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"不支持的提供商: {provider}。"
                f"支持: {', '.join(sorted(MANAGED_GATEWAY_CREDENTIAL_PROVIDERS))}"
            ),
        )
    return p


def validate_personal_model_provider(provider: str) -> str:
    p = provider.lower()
    if p not in PERSONAL_MODEL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"不支持的提供商: {provider}。"
                f"支持: {', '.join(sorted(PERSONAL_MODEL_PROVIDERS))}"
            ),
        )
    return p


def validate_optional_provider(provider: str | None) -> None:
    if provider is not None and provider not in PERSONAL_MODEL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的提供商: {provider}",
        )


def effective_model_type_query(*, model_type: str | None, mode: str | None) -> str | None:
    if model_type and model_type.strip():
        return model_type.strip()
    if not mode or not mode.strip():
        return None
    key = mode.strip().lower()
    return {"chat": "text", "image_gen": "image_gen", "video": "video"}.get(key)


def _gateway_management_reads(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementReadService:
    return GatewayManagementReadService(db)


def _gateway_management_writes(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayManagementWriteService:
    return GatewayManagementWriteService(db)


def _credential_upstream_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialUpstreamCatalogService:
    return CredentialUpstreamCatalogService(db)


MgmtReads = Annotated[GatewayManagementReadService, Depends(_gateway_management_reads)]
MgmtWrites = Annotated[GatewayManagementWriteService, Depends(_gateway_management_writes)]
CatalogSvc = Annotated[CredentialUpstreamCatalogService, Depends(_credential_upstream_catalog)]


def encryption_key() -> str:
    return derive_encryption_key(settings.secret_key.get_secret_value())


def vkey_to_response(record: GatewayVirtualKey) -> VirtualKeyResponse:
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


__all__ = [
    "CatalogSvc",
    "MgmtReads",
    "MgmtWrites",
    "credential_probe_to_response",
    "effective_model_type_query",
    "encryption_key",
    "validate_managed_credential_provider",
    "validate_optional_provider",
    "validate_personal_model_provider",
    "validate_user_credential_provider",
    "vkey_to_response",
]
