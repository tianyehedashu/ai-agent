"""ProviderCredentialRepository - 凭据仓储"""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.models.provider_credential import ProviderCredential


class ProviderCredentialRepository:
    """凭据仓储

    封装 system / team / user 三级 scope 的查询。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, credential_id: uuid.UUID) -> ProviderCredential | None:
        return await self._session.get(ProviderCredential, credential_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[ProviderCredential]:
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.scope == "user",
                ProviderCredential.scope_id == user_id,
            )
            .order_by(ProviderCredential.provider, ProviderCredential.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_team(
        self,
        team_id: uuid.UUID,
        *,
        include_system: bool = True,
    ) -> list[ProviderCredential]:
        clauses = [
            and_(
                ProviderCredential.scope == "team",
                ProviderCredential.scope_id == team_id,
            )
        ]
        if include_system:
            clauses.append(ProviderCredential.scope == "system")
        stmt = (
            select(ProviderCredential)
            .where(or_(*clauses))
            .order_by(ProviderCredential.scope, ProviderCredential.provider)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_system(self) -> list[ProviderCredential]:
        stmt = (
            select(ProviderCredential)
            .where(ProviderCredential.scope == "system")
            .order_by(ProviderCredential.provider, ProviderCredential.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID | None,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None = None,
        extra: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> ProviderCredential:
        credential = ProviderCredential(
            scope=scope,
            scope_id=scope_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            extra=extra,
            is_active=is_active,
        )
        self._session.add(credential)
        await self._session.flush()
        return credential

    async def update(
        self,
        credential_id: uuid.UUID,
        *,
        api_key_encrypted: str | None = None,
        api_base: str | None = None,
        extra: dict[str, Any] | None = None,
        is_active: bool | None = None,
        name: str | None = None,
    ) -> ProviderCredential | None:
        credential = await self.get(credential_id)
        if credential is None:
            return None
        if api_key_encrypted is not None:
            credential.api_key_encrypted = api_key_encrypted
        if api_base is not None:
            credential.api_base = api_base
        if extra is not None:
            credential.extra = extra
        if is_active is not None:
            credential.is_active = is_active
        if name is not None:
            credential.name = name
        await self._session.flush()
        return credential

    async def delete(self, credential_id: uuid.UUID) -> bool:
        credential = await self.get(credential_id)
        if credential is None:
            return False
        await self._session.delete(credential)
        await self._session.flush()
        return True

    async def copy_to_team(
        self,
        credential_id: uuid.UUID,
        team_id: uuid.UUID,
    ) -> ProviderCredential | None:
        """把一条用户/系统凭据复制为团队凭据（导入到 Gateway）"""
        source = await self.get(credential_id)
        if source is None:
            return None
        new_cred = ProviderCredential(
            scope="team",
            scope_id=team_id,
            provider=source.provider,
            name=source.name,
            api_key_encrypted=source.api_key_encrypted,
            api_base=source.api_base,
            extra=source.extra,
            is_active=True,
        )
        self._session.add(new_cred)
        await self._session.flush()
        return new_cred


__all__ = ["ProviderCredentialRepository"]
