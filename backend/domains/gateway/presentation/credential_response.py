"""将 ProviderCredential ORM 组装为带 api_key_masked 的管理 API 响应。"""

from __future__ import annotations

from binascii import Error as BinasciiError

from cryptography.fernet import InvalidToken

from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.gateway.presentation.schemas.common import CredentialResponse
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


def build_credential_response(
    cred: ProviderCredential,
    *,
    encryption_key: str,
) -> CredentialResponse:
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
    return CredentialResponse(
        id=cred.id,
        scope=cred.scope,
        scope_id=cred.scope_id,
        provider=cred.provider,
        name=cred.name,
        api_base=cred.api_base,
        extra=cred.extra,
        is_active=cred.is_active,
        created_at=cred.created_at,
        api_key_masked=api_key_masked,
    )


__all__ = ["build_credential_response", "mask_plain_secret_for_display"]
