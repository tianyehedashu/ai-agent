"""ProviderCredential / SystemProviderCredential ORM → CredentialReadModel。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.management.credential_read_model import CredentialReadModel

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential

    CredentialReadSource = (
        CredentialReadModel | ProviderCredential | SystemProviderCredential
    )
else:
    CredentialReadSource = CredentialReadModel


def credential_from_orm(cred: ProviderCredential) -> CredentialReadModel:
    return CredentialReadModel(
        id=cred.id,
        tenant_id=cred.tenant_id,
        scope=cred.scope,
        scope_id=cred.scope_id,
        provider=cred.provider,
        name=cred.name,
        api_base=cred.api_base,
        extra=cred.extra,
        is_active=cred.is_active,
        created_at=cred.created_at,
        api_key_encrypted=cred.api_key_encrypted,
        visibility=None,
    )


def system_credential_from_orm(cred: SystemProviderCredential) -> CredentialReadModel:
    return CredentialReadModel(
        id=cred.id,
        tenant_id=None,
        scope="system",
        scope_id=None,
        provider=cred.provider,
        name=cred.name,
        api_base=cred.api_base,
        extra=cred.extra,
        is_active=cred.is_active,
        created_at=cred.created_at,
        api_key_encrypted=cred.api_key_encrypted,
        visibility=cred.visibility,
    )


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
    "credential_from_orm",
    "ensure_credential_read_model",
    "system_credential_from_orm",
]
