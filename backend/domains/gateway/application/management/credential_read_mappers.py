"""ProviderCredential / SystemProviderCredential ORM → CredentialReadModel。"""

from __future__ import annotations

from binascii import Error as BinasciiError
from typing import TYPE_CHECKING

from cryptography.fernet import InvalidToken

from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.domain.upstream_endpoint import effective_api_bases_for_credential
from domains.gateway.domain.upstream_profile_registry import get_upstream_profile
from domains.gateway.presentation.credential_response import mask_plain_secret_for_display
from libs.crypto import decrypt_value

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential

    CredentialReadSource = (
        CredentialReadModel | ProviderCredential | SystemProviderCredential
    )
else:
    CredentialReadSource = CredentialReadModel


def _credential_profile_display(
    *,
    provider: str,
    profile_id: str | None,
    api_base: str | None,
) -> tuple[str, str | None, str | None]:
    profile = get_upstream_profile(profile_id, provider=provider)
    effective = effective_api_bases_for_credential(
        provider=provider,
        profile_id=profile_id,
        api_base=api_base,
    )
    return (
        profile.label,
        effective.get("openai_compat"),
        effective.get("anthropic_native"),
    )


def _mask_api_key_encrypted(api_key_encrypted: str, encryption_key: str) -> str:
    try:
        plain = decrypt_value(api_key_encrypted, encryption_key)
        return mask_plain_secret_for_display(plain)
    except (InvalidToken, BinasciiError, UnicodeDecodeError, ValueError):
        return "（无法展示）"


def credential_from_orm(
    cred: ProviderCredential,
    *,
    encryption_key: str | None = None,
) -> CredentialReadModel:
    api_key_masked = (
        _mask_api_key_encrypted(cred.api_key_encrypted, encryption_key)
        if encryption_key
        else None
    )
    profile_label, effective_openai, effective_anthropic = _credential_profile_display(
        provider=cred.provider,
        profile_id=cred.profile_id,
        api_base=cred.api_base,
    )
    return CredentialReadModel(
        id=cred.id,
        tenant_id=cred.tenant_id,
        scope=cred.scope,
        scope_id=cred.scope_id,
        provider=cred.provider,
        name=cred.name,
        api_base=cred.api_base,
        profile_id=cred.profile_id,
        profile_label=profile_label,
        effective_api_base_openai=effective_openai,
        effective_api_base_anthropic=effective_anthropic,
        extra=cred.extra,
        is_active=cred.is_active,
        created_at=cred.created_at,
        api_key_encrypted=cred.api_key_encrypted,
        visibility=None,
        api_key_masked=api_key_masked,
    )


def system_credential_from_orm(
    cred: SystemProviderCredential,
    *,
    encryption_key: str | None = None,
) -> CredentialReadModel:
    api_key_masked = (
        _mask_api_key_encrypted(cred.api_key_encrypted, encryption_key)
        if encryption_key
        else None
    )
    profile_label, effective_openai, effective_anthropic = _credential_profile_display(
        provider=cred.provider,
        profile_id=cred.profile_id,
        api_base=cred.api_base,
    )
    return CredentialReadModel(
        id=cred.id,
        tenant_id=None,
        scope="system",
        scope_id=None,
        provider=cred.provider,
        name=cred.name,
        api_base=cred.api_base,
        profile_id=cred.profile_id,
        profile_label=profile_label,
        effective_api_base_openai=effective_openai,
        effective_api_base_anthropic=effective_anthropic,
        extra=cred.extra,
        is_active=cred.is_active,
        created_at=cred.created_at,
        api_key_encrypted=cred.api_key_encrypted,
        visibility=cred.visibility,
        api_key_masked=api_key_masked,
    )


def bindable_credential_scope(cred: object) -> str:
    """团队模型写侧 bindable 凭据 → API scope（system / team / user）。"""
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential

    if isinstance(cred, SystemProviderCredential):
        return "system"
    if isinstance(cred, ProviderCredential):
        return cred.scope or "team"
    raise TypeError(f"unsupported bindable credential type: {type(cred)!r}")


def ensure_credential_read_model(cred: CredentialReadSource) -> CredentialReadModel:
    """ORM 或已映射的只读模型统一为 CredentialReadModel（写侧返回 ORM 时 presentation 复用）。"""
    if isinstance(cred, CredentialReadModel):
        return cred
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential

    if isinstance(cred, SystemProviderCredential):
        return system_credential_from_orm(cred)
    if isinstance(cred, ProviderCredential):
        return credential_from_orm(cred)
    raise TypeError(f"unsupported credential type: {type(cred)!r}")


__all__ = [
    "CredentialReadSource",
    "bindable_credential_scope",
    "credential_from_orm",
    "ensure_credential_read_model",
    "system_credential_from_orm",
]
