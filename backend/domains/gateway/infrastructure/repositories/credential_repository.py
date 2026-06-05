"""ProviderCredentialRepository - 凭据仓储"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, or_, select

from domains.gateway.domain.team_registry_credential_display import (
    TeamRegistryCredentialDisplay,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.gateway.infrastructure.repositories.system_credential_repository import (
    SystemProviderCredentialRepository,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential


@dataclass(frozen=True)
class EffectiveProviderSummary:
    provider: str
    credential_count: int
    has_managed: bool
    has_user: bool


class ProviderCredentialRepository:
    """租户凭据（``tenant_id``）与用户 BYOK（``scope=user``）；系统级见 ``system_provider_credentials``。"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, credential_id: uuid.UUID) -> ProviderCredential | None:
        return await self._session.get(ProviderCredential, credential_id)

    async def get_bindable_for_team_gateway_model(
        self,
        credential_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> ProviderCredential | SystemProviderCredential | None:
        row = await self.get(credential_id)
        if row is not None:
            if row.tenant_id == tenant_id:
                return row
            return None
        if is_platform_admin:
            return await SystemProviderCredentialRepository(self._session).get(credential_id)
        return None

    async def list_by_ids(self, credential_ids: list[uuid.UUID]) -> list[ProviderCredential]:
        if not credential_ids:
            return []
        stmt = select(ProviderCredential).where(ProviderCredential.id.in_(credential_ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_distinct_for_team_registry_in_tenants(
        self,
        tenant_ids: list[uuid.UUID],
    ) -> list[TeamRegistryCredentialDisplay]:
        """协作团队注册模型绑定的凭据（去重，供跨团队模型列表筛选下拉）。"""
        if not tenant_ids:
            return []
        stmt = (
            select(
                ProviderCredential.id,
                ProviderCredential.name,
                ProviderCredential.provider,
                ProviderCredential.tenant_id,
            )
            .join(GatewayModel, GatewayModel.credential_id == ProviderCredential.id)
            .where(
                GatewayModel.tenant_id.in_(tenant_ids),
                ProviderCredential.tenant_id.in_(tenant_ids),
            )
            .distinct()
            .order_by(ProviderCredential.tenant_id, ProviderCredential.name)
        )
        result = await self._session.execute(stmt)
        return [
            TeamRegistryCredentialDisplay(
                id=row.id,
                name=row.name,
                provider=row.provider,
                tenant_id=row.tenant_id,
            )
            for row in result.all()
            if row.tenant_id is not None
        ]

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

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID,
        *,
        include_system: bool = True,
    ) -> list[ProviderCredential]:
        stmt = (
            select(ProviderCredential)
            .where(ProviderCredential.tenant_id == tenant_id)
            .order_by(ProviderCredential.provider, ProviderCredential.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    def _team_scope_for_tenants_stmt(self, tenant_ids: list[uuid.UUID]):
        return (
            select(ProviderCredential)
            .where(
                ProviderCredential.tenant_id.in_(tenant_ids),
                or_(
                    ProviderCredential.scope.is_(None),
                    ProviderCredential.scope == "team",
                ),
            )
            .order_by(ProviderCredential.tenant_id, ProviderCredential.name)
        )

    async def count_team_scope_for_tenants(self, tenant_ids: list[uuid.UUID]) -> int:
        if not tenant_ids:
            return 0
        stmt = select(func.count(ProviderCredential.id)).where(
            ProviderCredential.tenant_id.in_(tenant_ids),
            or_(
                ProviderCredential.scope.is_(None),
                ProviderCredential.scope == "team",
            ),
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def list_tenant_ids_with_team_scope_for_tenants(
        self, tenant_ids: list[uuid.UUID]
    ) -> list[uuid.UUID]:
        """给定 tenant 集合，返回其中至少有一条 team-scope 凭据的 tenant_id（去重）。"""
        if not tenant_ids:
            return []
        stmt = (
            select(ProviderCredential.tenant_id)
            .where(
                ProviderCredential.tenant_id.in_(tenant_ids),
                ProviderCredential.tenant_id.is_not(None),
                or_(
                    ProviderCredential.scope.is_(None),
                    ProviderCredential.scope == "team",
                ),
            )
            .distinct()
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def list_team_scope_for_tenants_page(
        self,
        tenant_ids: list[uuid.UUID],
        *,
        offset: int,
        limit: int,
    ) -> list[ProviderCredential]:
        if not tenant_ids:
            return []
        stmt = self._team_scope_for_tenants_stmt(tenant_ids).offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_effective_provider_summaries(self) -> list[EffectiveProviderSummary]:
        stmt = (
            select(
                ProviderCredential.provider,
                ProviderCredential.scope,
                ProviderCredential.tenant_id,
                func.count(ProviderCredential.id),
            )
            .where(ProviderCredential.is_active.is_(True))
            .group_by(
                ProviderCredential.provider,
                ProviderCredential.scope,
                ProviderCredential.tenant_id,
            )
            .order_by(ProviderCredential.provider)
        )
        result = await self._session.execute(stmt)
        by_provider: dict[str, dict[str, int | bool]] = {}
        for provider, scope, tenant_id, count in result.all():
            item = by_provider.setdefault(
                provider,
                {"credential_count": 0, "has_managed": False, "has_user": False},
            )
            item["credential_count"] = int(item["credential_count"]) + int(count)
            if scope == "user":
                item["has_user"] = True
            elif tenant_id is not None:
                item["has_managed"] = True
        return [
            EffectiveProviderSummary(
                provider=provider,
                credential_count=int(payload["credential_count"]),
                has_managed=bool(payload["has_managed"]),
                has_user=bool(payload["has_user"]),
            )
            for provider, payload in by_provider.items()
        ]

    async def create(
        self,
        *,
        tenant_id: uuid.UUID | None = None,
        scope: str | None = None,
        scope_id: uuid.UUID | None = None,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None = None,
        api_bases: dict[str, Any] | None = None,
        profile_id: str | None = None,
        extra: dict[str, Any] | None = None,
        is_active: bool = True,
        created_by_user_id: uuid.UUID | None = None,
    ) -> ProviderCredential:
        credential = ProviderCredential(
            tenant_id=tenant_id,
            scope=scope,
            scope_id=scope_id,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            api_bases=api_bases,
            profile_id=profile_id,
            extra=extra,
            is_active=is_active,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(credential)
        await self._session.flush()
        return credential

    async def create_for_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        provider: str,
        name: str,
        api_key_encrypted: str,
        api_base: str | None = None,
        api_bases: dict[str, Any] | None = None,
        profile_id: str | None = None,
        extra: dict[str, Any] | None = None,
        is_active: bool = True,
        created_by_user_id: uuid.UUID | None = None,
    ) -> ProviderCredential:
        return await self.create(
            tenant_id=tenant_id,
            scope=None,
            scope_id=None,
            provider=provider,
            name=name,
            api_key_encrypted=api_key_encrypted,
            api_base=api_base,
            api_bases=api_bases,
            profile_id=profile_id,
            extra=extra,
            is_active=is_active,
            created_by_user_id=created_by_user_id,
        )

    async def update(
        self,
        credential_id: uuid.UUID,
        *,
        api_key_encrypted: str | None = None,
        api_base: str | None = None,
        api_bases: dict[str, Any] | None = None,
        profile_id: str | None = None,
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
        if api_bases is not None:
            credential.api_bases = api_bases
        if profile_id is not None:
            credential.profile_id = profile_id
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

    async def find_tenant_by_provider_and_name(
        self, tenant_id: uuid.UUID, provider: str, name: str
    ) -> ProviderCredential | None:
        stmt = (
            select(ProviderCredential)
            .where(
                ProviderCredential.tenant_id == tenant_id,
                ProviderCredential.provider == provider,
                ProviderCredential.name == name,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def copy_to_team(
        self,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        created_by_user_id: uuid.UUID | None = None,
        name_override: str | None = None,
    ) -> ProviderCredential | None:
        source = await self.get(credential_id)
        if source is None:
            return None
        new_cred = ProviderCredential(
            tenant_id=tenant_id,
            scope=None,
            scope_id=None,
            provider=source.provider,
            name=name_override or source.name,
            api_key_encrypted=source.api_key_encrypted,
            api_base=source.api_base,
            api_bases=source.api_bases,
            profile_id=source.profile_id,
            extra=source.extra,
            is_active=True,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(new_cred)
        await self._session.flush()
        return new_cred


__all__ = [
    "EffectiveProviderSummary",
    "ProviderCredentialRepository",
    "TeamRegistryCredentialDisplay",
]
