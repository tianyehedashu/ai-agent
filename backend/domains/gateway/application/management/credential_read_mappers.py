"""ProviderCredential ORM → CredentialReadModel。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.management.credential_read_model import CredentialReadModel

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential


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
    )


__all__ = ["credential_from_orm", "system_credential_from_orm"]
