"""ProviderCredentialRepository - 凭据仓储"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, or_, select

from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    CONFIG_MANAGED_CREDENTIAL_NAME,
)
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ProviderCredentialRepository:
    """凭据仓储

    封装 system / team / user 三级 scope 的查询。
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, credential_id: uuid.UUID) -> ProviderCredential | None:
        return await self._session.get(ProviderCredential, credential_id)

    async def get_bindable_for_team_gateway_model(
        self,
        credential_id: uuid.UUID,
        *,
        team_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> ProviderCredential | None:
        """团队注册或更新 ``GatewayModel`` 时可绑定的凭据。

        与 ``GatewayManagementReadService.get_managed_credential_for_team`` 可见集合一致：
        当前 ``team_id`` 下 ``scope=team`` 的凭据，或（``is_platform_admin`` 为真时）``scope=system``。
        ``user`` scope 不可直接绑定团队模型。
        """
        row = await self.get(credential_id)
        if row is None:
            return None
        if row.scope == "team" and row.scope_id == team_id:
            return row
        if row.scope == "system" and is_platform_admin:
            return row
        return None

    async def list_by_ids(self, credential_ids: list[uuid.UUID]) -> list[ProviderCredential]:
        if not credential_ids:
            return []
        stmt = select(ProviderCredential).where(ProviderCredential.id.in_(credential_ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

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

    async def list_user_by_provider(
        self, user_id: uuid.UUID, provider: str
    ) -> list[ProviderCredential]:
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.scope == "user",
                ProviderCredential.scope_id == user_id,
                ProviderCredential.provider == provider,
            )
            .order_by(ProviderCredential.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_user_by_provider_and_name(
        self, user_id: uuid.UUID, provider: str, name: str
    ) -> ProviderCredential | None:
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.scope == "user",
                ProviderCredential.scope_id == user_id,
                ProviderCredential.provider == provider,
                ProviderCredential.name == name,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

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

    async def find_system_by_provider_and_name(
        self, provider: str, name: str
    ) -> ProviderCredential | None:
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.scope == "system",
                ProviderCredential.scope_id.is_(None),
                ProviderCredential.provider == provider,
                ProviderCredential.name == name,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_system_config_managed(self, provider: str) -> ProviderCredential | None:
        """配置同步托管的系统凭据：按固定名或 extra.managed_by=config 查找（避免重命名后重复创建）。"""
        by_name = await self.find_system_by_provider_and_name(
            provider, CONFIG_MANAGED_CREDENTIAL_NAME
        )
        if by_name is not None:
            return by_name
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.scope == "system",
                ProviderCredential.scope_id.is_(None),
                ProviderCredential.provider == provider,
                ProviderCredential.extra.isnot(None),
                ProviderCredential.extra["managed_by"].astext == CONFIG_MANAGED_BY,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        tagged = result.scalar_one_or_none()
        if tagged is not None:
            return tagged
        stmt_all = (
            select(ProviderCredential)
            .where(
                ProviderCredential.scope == "system",
                ProviderCredential.scope_id.is_(None),
                ProviderCredential.provider == provider,
            )
            .order_by(ProviderCredential.name)
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
