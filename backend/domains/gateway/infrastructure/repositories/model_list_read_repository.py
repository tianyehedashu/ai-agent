"""Gateway 模型列表分页读仓储（SQL 路径单一入口）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.catalog.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.model_list_sql import (
    build_system_list_stmt,
    build_tenant_list_stmt,
    build_tenants_list_stmt,
    count_from_stmt,
    list_tenant_ids_with_team_registry_for_tenants,
    summarize_system_list,
    summarize_tenant_list,
    summarize_tenants_list,
)

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class ModelListReadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def paginate_system(
        self,
        *,
        only_enabled: bool,
        capability: str | None,
        provider: str | None,
        credential_id: uuid.UUID | None,
        enabled: bool | None,
        q: str | None,
        connectivity: ModelListConnectivityFilter,
        sort_field: ModelListSortField,
        order: ModelListSortOrder,
        offset: int,
        limit: int,
    ) -> tuple[list[SystemGatewayModel], int, dict[str, int]]:
        base = build_system_list_stmt(
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
            enabled=enabled,
            q=q,
            connectivity=connectivity,
            sort_field=sort_field,
            order=order,
        )
        total = await count_from_stmt(self._session, base)
        page_stmt = base.offset(offset).limit(limit)
        result = await self._session.execute(page_stmt)
        items = list(result.scalars().all())
        summary = await summarize_system_list(
            self._session,
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
            enabled=enabled,
            q=q,
        )
        return items, total, summary

    async def paginate_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        only_enabled: bool,
        capability: str | None,
        provider: str | None,
        credential_id: uuid.UUID | None,
        exclude_user_scope_credentials: bool,
        enabled: bool | None,
        q: str | None,
        connectivity: ModelListConnectivityFilter,
        sort_field: ModelListSortField,
        order: ModelListSortOrder,
        offset: int,
        limit: int,
        readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
        user_scope_owner_id: uuid.UUID | None = None,
    ) -> tuple[list[GatewayModel], int, dict[str, int]]:
        base = build_tenant_list_stmt(
            tenant_id=tenant_id,
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
            exclude_user_scope_credentials=exclude_user_scope_credentials,
            enabled=enabled,
            q=q,
            connectivity=connectivity,
            sort_field=sort_field,
            order=order,
            readable_team_credential_ids=readable_team_credential_ids,
            user_scope_owner_id=user_scope_owner_id,
        )
        total = await count_from_stmt(self._session, base)
        page_stmt = base.offset(offset).limit(limit)
        result = await self._session.execute(page_stmt)
        items = list(result.scalars().all())
        summary = await summarize_tenant_list(
            self._session,
            tenant_id=tenant_id,
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
            exclude_user_scope_credentials=exclude_user_scope_credentials,
            enabled=enabled,
            q=q,
            readable_team_credential_ids=readable_team_credential_ids,
            user_scope_owner_id=user_scope_owner_id,
        )
        return items, total, summary

    async def paginate_tenants(
        self,
        *,
        tenant_ids: list[uuid.UUID],
        only_enabled: bool,
        capability: str | None,
        provider: str | None,
        credential_id: uuid.UUID | None,
        exclude_user_scope_credentials: bool,
        enabled: bool | None,
        q: str | None,
        connectivity: ModelListConnectivityFilter,
        sort_field: ModelListSortField,
        order: ModelListSortOrder,
        offset: int,
        limit: int,
        readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
    ) -> tuple[list[GatewayModel], int, dict[str, int]]:
        base = build_tenants_list_stmt(
            tenant_ids=tenant_ids,
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
            exclude_user_scope_credentials=exclude_user_scope_credentials,
            enabled=enabled,
            q=q,
            connectivity=connectivity,
            sort_field=sort_field,
            order=order,
            readable_team_credential_ids=readable_team_credential_ids,
        )
        total = await count_from_stmt(self._session, base)
        page_stmt = base.offset(offset).limit(limit)
        result = await self._session.execute(page_stmt)
        items = list(result.scalars().all())
        summary = await summarize_tenants_list(
            self._session,
            tenant_ids=tenant_ids,
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
            exclude_user_scope_credentials=exclude_user_scope_credentials,
            enabled=enabled,
            q=q,
            readable_team_credential_ids=readable_team_credential_ids,
        )
        return items, total, summary

    async def list_tenant_ids_with_team_registry(
        self,
        tenant_ids: list[uuid.UUID],
        *,
        exclude_user_scope_credentials: bool,
        only_enabled: bool = False,
        capability: str | None = None,
        provider: str | None = None,
        credential_id: uuid.UUID | None = None,
        enabled: bool | None = None,
        q: str | None = None,
        connectivity: ModelListConnectivityFilter = ModelListConnectivityFilter.ALL,
        readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
    ) -> list[uuid.UUID]:
        return await list_tenant_ids_with_team_registry_for_tenants(
            self._session,
            tenant_ids=tenant_ids,
            exclude_user_scope_credentials=exclude_user_scope_credentials,
            only_enabled=only_enabled,
            capability=capability,
            provider=provider,
            credential_id=credential_id,
            enabled=enabled,
            q=q,
            connectivity=connectivity,
            readable_team_credential_ids=readable_team_credential_ids,
        )


__all__ = ["ModelListReadRepository"]
