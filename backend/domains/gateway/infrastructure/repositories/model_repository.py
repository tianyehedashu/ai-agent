"""GatewayModelRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from domains.gateway.domain.policies.model_selection import merge_named_rows_tenant_overrides_system
from domains.gateway.domain.types import (
    CONFIG_MANAGED_BY,
    GATEWAY_MODEL_MANAGED_BY_TAG,
    CredentialScope,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.gateway_route_repository import (
    GatewayRouteRepository,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

class GatewayModelRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, model_id: uuid.UUID) -> GatewayModel | None:
        return await self._session.get(GatewayModel, model_id)

    async def list_name_real_model_pairs_for_credential(
        self, credential_id: uuid.UUID
    ) -> list[tuple[str, str]]:
        """凭据下已注册模型的 (注册别名, real_model)。"""
        stmt = (
            select(GatewayModel.name, GatewayModel.real_model)
            .where(GatewayModel.credential_id == credential_id)
            .order_by(GatewayModel.name)
        )
        result = await self._session.execute(stmt)
        return [(str(row[0]), str(row[1])) for row in result.all()]

    async def list_system(
        self,
        *,
        only_enabled: bool = True,
        capability: str | None = None,
        provider: str | None = None,
        credential_id: uuid.UUID | None = None,
    ) -> list[SystemGatewayModel]:
        clauses: list[object] = []
        if only_enabled:
            clauses.append(SystemGatewayModel.enabled.is_(True))
        if capability:
            clauses.append(SystemGatewayModel.capability == capability)
        if provider is not None:
            clauses.append(SystemGatewayModel.provider == provider)
        if credential_id is not None:
            clauses.append(SystemGatewayModel.credential_id == credential_id)
        stmt = select(SystemGatewayModel).where(*clauses).order_by(SystemGatewayModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_tenant_owned(
        self,
        tenant_id: uuid.UUID,
        *,
        only_enabled: bool = True,
        capability: str | None = None,
        provider: str | None = None,
        credential_id: uuid.UUID | None = None,
        exclude_user_scope_credentials: bool = False,
    ) -> list[GatewayModel]:
        clauses = [GatewayModel.tenant_id == tenant_id]
        if only_enabled:
            clauses.append(GatewayModel.enabled.is_(True))
        if capability:
            clauses.append(GatewayModel.capability == capability)
        if provider is not None:
            clauses.append(GatewayModel.provider == provider)
        if credential_id is not None:
            clauses.append(GatewayModel.credential_id == credential_id)
        if exclude_user_scope_credentials:
            user_scoped_subq = select(ProviderCredential.id).where(
                ProviderCredential.scope == CredentialScope.USER.value
            )
            clauses.append(GatewayModel.credential_id.notin_(user_scoped_subq))
        stmt = select(GatewayModel).where(*clauses).order_by(GatewayModel.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_tenant(
        self,
        tenant_id: uuid.UUID | None,
        *,
        only_enabled: bool = True,
        capability: str | None = None,
        provider: str | None = None,
        credential_id: uuid.UUID | None = None,
    ) -> list[GatewayModel]:
        """tenant + system 行合并（无可见性过滤；过滤见 ``gateway_model_listing``）。"""
        if tenant_id is None:
            return list(
                await self.list_system(
                    only_enabled=only_enabled,
                    capability=capability,
                    provider=provider,
                    credential_id=credential_id,
                )
            )
        tenant_rows = await self.list_tenant_owned(
            tenant_id,
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
        )
        system_rows = await self.list_system(
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
        )
        return merge_named_rows_tenant_overrides_system(tenant_rows, system_rows)

    async def get_for_tenant(self, model_id: uuid.UUID, tenant_id: uuid.UUID) -> GatewayModel | None:
        row = await self.get(model_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return row

    async def get_on_team(self, model_id: uuid.UUID, team_id: uuid.UUID) -> GatewayModel | None:
        import warnings

        warnings.warn(
            "get_on_team is deprecated; use get_for_tenant",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.get_for_tenant(model_id, team_id)

    async def name_exists_for_tenant(
        self,
        tenant_id: uuid.UUID,
        name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        clauses = [GatewayModel.tenant_id == tenant_id, GatewayModel.name == name]
        if exclude_id is not None:
            clauses.append(GatewayModel.id != exclude_id)
        stmt = select(func.count()).select_from(GatewayModel).where(*clauses)
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0) > 0

    async def name_exists_on_team(
        self,
        team_id: uuid.UUID,
        name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        import warnings

        warnings.warn(
            "name_exists_on_team is deprecated; use name_exists_for_tenant",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.name_exists_for_tenant(team_id, name, exclude_id=exclude_id)

    async def name_exists_in_scope(
        self,
        tenant_id: uuid.UUID | None,
        name: str,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """``tenant_id`` 为 ``None`` 时检查全局模型名；否则等同 ``name_exists_for_tenant``。"""
        if tenant_id is not None:
            return await self.name_exists_for_tenant(tenant_id, name, exclude_id=exclude_id)
        sys = await self.get_system_by_name(name)
        if sys is None:
            return False
        return exclude_id is None or sys.id != exclude_id

    async def list_all_active(self) -> list[GatewayModel]:
        stmt = select(GatewayModel).where(GatewayModel.enabled.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_system_by_name(self, name: str) -> SystemGatewayModel | None:
        stmt = select(SystemGatewayModel).where(SystemGatewayModel.name == name).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_system(self, model_id: uuid.UUID) -> SystemGatewayModel | None:
        return await self._session.get(SystemGatewayModel, model_id)

    async def get_by_name(self, tenant_id: uuid.UUID | None, name: str) -> GatewayModel | None:
        if tenant_id is None:
            return None
        stmt = (
            select(GatewayModel)
            .where(GatewayModel.name == name, GatewayModel.tenant_id == tenant_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_by_name(
        self, tenant_id: uuid.UUID | None, name: str
    ) -> GatewayModel | SystemGatewayModel | None:
        """租户行优先；无租户行时回退 system 表（用于路由解析）。"""
        if tenant_id is not None:
            tenant_row = await self.get_by_name(tenant_id, name)
            if tenant_row is not None:
                return tenant_row
        return await self.get_system_by_name(name)

    async def create_system(
        self,
        *,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int = 1,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        tags: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> SystemGatewayModel:
        row = SystemGatewayModel(
            name=name,
            capability=capability,
            real_model=real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=tags,
            enabled=enabled,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def create(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        capability: str,
        real_model: str,
        credential_id: uuid.UUID,
        provider: str,
        weight: int = 1,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        tags: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> GatewayModel:
        model = GatewayModel(
            tenant_id=tenant_id,
            name=name,
            capability=capability,
            real_model=real_model,
            credential_id=credential_id,
            provider=provider,
            weight=weight,
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
            tags=tags,
            enabled=enabled,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def update(
        self,
        model_id: uuid.UUID,
        **fields: Any,
    ) -> GatewayModel | None:
        model = await self.get(model_id)
        if model is None:
            return None
        for key, value in fields.items():
            if not hasattr(model, key):
                continue
            # last_test_reason=None 表示成功测试后清空上次失败说明
            if key == "last_test_reason" or isinstance(value, bool) or value is not None:
                setattr(model, key, value)
        await self._session.flush()
        return model

    async def update_system(
        self,
        model_id: uuid.UUID,
        **fields: Any,
    ) -> SystemGatewayModel | None:
        model = await self._session.get(SystemGatewayModel, model_id)
        if model is None:
            return None
        for key, value in fields.items():
            if not hasattr(model, key):
                continue
            if key == "last_test_reason" or isinstance(value, bool) or value is not None:
                setattr(model, key, value)
        await self._session.flush()
        return model

    async def list_by_credential_id(self, credential_id: uuid.UUID) -> list[GatewayModel]:
        stmt = (
            select(GatewayModel)
            .where(GatewayModel.credential_id == credential_id)
            .order_by(GatewayModel.tenant_id.nulls_first(), GatewayModel.name)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def has_config_managed_global_for_credential(self, credential_id: uuid.UUID) -> bool:
        stmt = (
            select(func.count())
            .select_from(SystemGatewayModel)
            .where(
                SystemGatewayModel.credential_id == credential_id,
                SystemGatewayModel.tags.isnot(None),
                SystemGatewayModel.tags[GATEWAY_MODEL_MANAGED_BY_TAG].astext == CONFIG_MANAGED_BY,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0) > 0

    async def count_by_credential_id(self, credential_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(GatewayModel)
            .where(GatewayModel.credential_id == credential_id)
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_models_grouped_by_credential(self) -> list[tuple[uuid.UUID, int]]:
        stmt = (
            select(GatewayModel.credential_id, func.count(GatewayModel.id))
            .group_by(GatewayModel.credential_id)
            .order_by(GatewayModel.credential_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(cid, int(cnt or 0)) for cid, cnt in rows]

    async def count_system_models_grouped_by_credential(
        self,
    ) -> list[tuple[uuid.UUID, int]]:
        stmt = (
            select(SystemGatewayModel.credential_id, func.count(SystemGatewayModel.id))
            .group_by(SystemGatewayModel.credential_id)
            .order_by(SystemGatewayModel.credential_id)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(cid, int(cnt or 0)) for cid, cnt in rows]

    async def delete(self, model_id: uuid.UUID) -> bool:
        model = await self.get(model_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def delete_system(self, model_id: uuid.UUID) -> bool:
        model = await self.get_system(model_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True


__all__ = ["GatewayModelRepository", "GatewayRouteRepository"]
