"""SystemProviderCredentialRepository - 系统级凭据仓储"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    CONFIG_MANAGED_CREDENTIAL_NAME,
)
from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class SystemProviderCredentialRepository:
    """``system_provider_credentials`` 表读写。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, credential_id: uuid.UUID) -> SystemProviderCredential | None:
        return await self._session.get(SystemProviderCredential, credential_id)

    async def list_all(self) -> list[SystemProviderCredential]:
        stmt = select(SystemProviderCredential).order_by(
            SystemProviderCredential.provider,
            SystemProviderCredential.name,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(
        self, credential_ids: set[uuid.UUID] | list[uuid.UUID]
    ) -> list[SystemProviderCredential]:
        ids = list(credential_ids)
        if not ids:
            return []
        stmt = select(SystemProviderCredential).where(SystemProviderCredential.id.in_(ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_provider_and_name(
        self, provider: str, name: str
    ) -> SystemProviderCredential | None:
        stmt = (
            select(SystemProviderCredential)
            .where(
                SystemProviderCredential.provider == provider,
                SystemProviderCredential.name == name,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_config_managed(self, provider: str) -> SystemProviderCredential | None:
        by_name = await self.find_by_provider_and_name(provider, CONFIG_MANAGED_CREDENTIAL_NAME)
        if by_name is not None:
            return by_name
        stmt = (
            select(SystemProviderCredential)
            .where(
                SystemProviderCredential.provider == provider,
                SystemProviderCredential.extra.isnot(None),
                SystemProviderCredential.extra["managed_by"].astext == CONFIG_MANAGED_BY,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        tagged = result.scalar_one_or_none()
        if tagged is not None:
            return tagged
        stmt_all = (
            select(SystemProviderCredential)
            .where(SystemProviderCredential.provider == provider)
            .order_by(SystemProviderCredential.name)
        )
        all_for_provider = list((await self._session.execute(stmt_all)).scalars().all())
        if len(all_for_provider) == 1:
            only = all_for_provider[0]
            model_repo = GatewayModelRepository(self._session)
            if await model_repo.has_config_managed_global_for_credential(only.id):
                return only
        return None

    async def create(
        self,
        *,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None = None,
        extra: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> SystemProviderCredential:
        row = SystemProviderCredential(
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
            is_active=is_active,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(
        self,
        credential_id: uuid.UUID,
        *,
        api_key_encrypted: str | None = None,
        api_base: str | None = None,
        extra: dict[str, Any] | None = None,
        is_active: bool | None = None,
        name: str | None = None,
        visibility: str | None = None,
    ) -> SystemProviderCredential | None:
        row = await self.get(credential_id)
        if row is None:
            return None
        if api_key_encrypted is not None:
            row.api_key_encrypted = api_key_encrypted
        if api_base is not None:
            row.api_base = api_base
        if extra is not None:
            row.extra = extra
        if is_active is not None:
            row.is_active = is_active
        if name is not None:
            row.name = name
        if visibility is not None:
            row.visibility = visibility
        await self._session.flush()
        return row

    async def delete(self, credential_id: uuid.UUID) -> bool:
        row = await self.get(credential_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


__all__ = ["SystemProviderCredentialRepository"]
