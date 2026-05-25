"""Gateway 模型列表分页读仓储（SQL 路径单一入口）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.domain.policies.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.model_list_sql import (
    build_system_list_stmt,
    build_tenant_list_stmt,
    count_from_stmt,
    summarize_system_list,
    summarize_tenant_list,
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
        )
        return items, total, summary


__all__ = ["ModelListReadRepository"]
