"""Gateway 单测：租户凭据种子数据。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from libs.crypto import derive_encryption_key, encrypt_value

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.provider_credential import ProviderCredential


def team_owner_actor_kw(test_user) -> dict[str, object]:
    """团队 owner 写操作 IAM 上下文（单测通用）。"""
    return {"actor_user_id": test_user.id, "team_role": "owner"}


async def create_tenant_test_credential(
    db_session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    provider: str = "openai",
    name: str,
    api_base: str | None = None,
    extra: dict[str, Any] | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> ProviderCredential:
    encryption_key = derive_encryption_key(settings.secret_key.get_secret_value())
    return await ProviderCredentialRepository(db_session).create_for_tenant(
        tenant_id=tenant_id,
        provider=provider,
        name=name,
        api_key_encrypted=encrypt_value("sk-fake", encryption_key),
        api_base=api_base,
        extra=extra,
        created_by_user_id=created_by_user_id,
    )
