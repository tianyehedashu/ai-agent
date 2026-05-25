"""将 CredentialReadModel 组装为带 api_key_masked 的管理 API 响应。"""

from __future__ import annotations

from binascii import Error as BinasciiError

from cryptography.fernet import InvalidToken

from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.domain.errors import CredentialApiKeyDecryptError
from domains.gateway.domain.types import (
    credential_api_scope,
    is_config_managed_system_credential,
)
from domains.gateway.domain.visibility import credential_visibility_for_api
from domains.gateway.presentation.schemas.common import (
    CredentialResponse,
    CredentialSummaryResponse,
)
from libs.crypto import decrypt_value
from utils.logging import get_logger

logger = get_logger(__name__)


def mask_plain_secret_for_display(plain: str) -> str:
    """对 API Key 类字符串做展示用掩码（不回传明文）。"""
    s = plain.strip()
    if len(s) <= 8:
        return "••••"
    prefix = s[:4]
    suffix = s[-4:]
    return f"{prefix}…{suffix}"


def decrypt_credential_api_key_for_reveal(
    cred: CredentialReadModel,
    *,
    encryption_key: str,
) -> str:
    """解密凭据中的 API Key（仅用于显式 reveal 接口，不写入列表/详情 DTO）。"""
    try:
        return decrypt_value(cred.api_key_encrypted, encryption_key).strip()
    except (InvalidToken, BinasciiError, UnicodeDecodeError, ValueError) as exc:
        logger.warning(
            "credential api_key reveal decrypt failed credential_id=%s exc_type=%s",
            cred.id,
            type(exc).__name__,
        )
        raise CredentialApiKeyDecryptError from exc


def build_credential_response(
    cred: CredentialReadModel,
    *,
    encryption_key: str,
) -> CredentialResponse:
    if cred.api_key_masked is not None:
        api_key_masked = cred.api_key_masked
    else:
        try:
            plain = decrypt_value(cred.api_key_encrypted, encryption_key)
            api_key_masked = mask_plain_secret_for_display(plain)
        except (InvalidToken, BinasciiError, UnicodeDecodeError, ValueError) as exc:
            logger.warning(
                "credential api_key_masked decrypt failed credential_id=%s exc_type=%s",
                cred.id,
                type(exc).__name__,
            )
            api_key_masked = "（无法展示）"
    api_scope = credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id)
    vis = credential_visibility_for_api(cred.visibility) if api_scope == "system" else None
    return CredentialResponse(
        id=cred.id,
        tenant_id=cred.tenant_id,
        scope=api_scope,
        scope_id=cred.scope_id,
        provider=cred.provider,
        name=cred.name,
        api_base=cred.api_base,
        extra=cred.extra,
        is_active=cred.is_active,
        is_config_managed=is_config_managed_system_credential(
            scope=cred.scope,
            tenant_id=cred.tenant_id,
            name=cred.name,
            extra=cred.extra,
        ),
        visibility=vis,
        created_at=cred.created_at,
        api_key_masked=api_key_masked,
    )


def build_credential_summary_response(cred: CredentialReadModel) -> CredentialSummaryResponse:
    """凭据摘要 DTO（无密钥）；读/写侧均应先映射为 CredentialReadModel。"""
    return CredentialSummaryResponse(
        id=cred.id,
        provider=cred.provider,
        name=cred.name,
        scope=credential_api_scope(scope=cred.scope, tenant_id=cred.tenant_id),
        is_active=cred.is_active,
        is_config_managed=is_config_managed_system_credential(
            scope=cred.scope,
            tenant_id=cred.tenant_id,
            name=cred.name,
            extra=cred.extra,
        ),
    )


__all__ = [
    "build_credential_response",
    "build_credential_summary_response",
    "decrypt_credential_api_key_for_reveal",
    "mask_plain_secret_for_display",
]
