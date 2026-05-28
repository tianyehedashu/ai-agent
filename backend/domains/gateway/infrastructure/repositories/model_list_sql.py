"""Gateway 模型列表 SQL 筛选与排序（仓储层）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import ColumnElement, and_, case, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from domains.gateway.domain.policies.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
)
from domains.gateway.domain.types import CredentialScope
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.provider_credential import ProviderCredential
from domains.gateway.infrastructure.models.system_gateway import (
    SystemGatewayModel,
    SystemProviderCredential,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.selectable import Select


def _connectivity_clause(
    status_col: InstrumentedAttribute[str | None],
    connectivity: ModelListConnectivityFilter,
) -> ColumnElement[bool] | None:
    if connectivity == ModelListConnectivityFilter.ALL:
        return None
    if connectivity == ModelListConnectivityFilter.SUCCESS:
        return status_col == "success"
    if connectivity == ModelListConnectivityFilter.FAILED:
        return status_col == "failed"
    return status_col.is_(None)


def _search_clause(
    *,
    name_col: InstrumentedAttribute[str],
    real_model_col: InstrumentedAttribute[str],
    provider_col: InstrumentedAttribute[str],
    q: str | None,
) -> ColumnElement[bool] | None:
    if not q or not q.strip():
        return None
    pattern = f"%{q.strip()}%"
    return or_(
        name_col.ilike(pattern),
        real_model_col.ilike(pattern),
        provider_col.ilike(pattern),
    )


def _credential_name_search_clause(
    credential_id_col: InstrumentedAttribute[Any],
    *,
    q: str | None,
    system_credential: bool,
    readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
    user_scope_owner_id: uuid.UUID | None = None,
) -> ColumnElement[bool] | None:
    if not q or not q.strip():
        return None
    if (
        readable_team_credential_ids is not None
        and len(readable_team_credential_ids) == 0
        and user_scope_owner_id is None
    ):
        return None
    pattern = f"%{q.strip()}%"
    cred_cls = SystemProviderCredential if system_credential else ProviderCredential
    cred_where: list[ColumnElement[bool]] = [
        cred_cls.id == credential_id_col,
        cred_cls.name.ilike(pattern),
    ]
    if readable_team_credential_ids is not None:
        cred_where.append(cred_cls.id.in_(readable_team_credential_ids))
    if user_scope_owner_id is not None:
        cred_where.append(cred_cls.scope == CredentialScope.USER.value)
        cred_where.append(cred_cls.scope_id == user_scope_owner_id)
    return select(cred_cls.id).where(*cred_where).exists()


def _registry_q_clause(
    *,
    name_col: InstrumentedAttribute[str],
    real_model_col: InstrumentedAttribute[str],
    provider_col: InstrumentedAttribute[str],
    credential_id_col: InstrumentedAttribute[Any],
    q: str | None,
    system_credential: bool,
    readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
    user_scope_owner_id: uuid.UUID | None = None,
) -> ColumnElement[bool] | None:
    model_search = _search_clause(
        name_col=name_col,
        real_model_col=real_model_col,
        provider_col=provider_col,
        q=q,
    )
    cred_search = _credential_name_search_clause(
        credential_id_col,
        q=q,
        system_credential=system_credential,
        readable_team_credential_ids=readable_team_credential_ids,
        user_scope_owner_id=user_scope_owner_id,
    )
    if model_search is None and cred_search is None:
        return None
    if model_search is None:
        return cred_search
    if cred_search is None:
        return model_search
    return or_(model_search, cred_search)


def _availability_order(model_cls: type[GatewayModel] | type[SystemGatewayModel]) -> ColumnElement[int]:
    """ORDER BY tier；镜像 domain ``is_registry_connectivity_available``（不含 entitlement）。"""
    return case(
        (
            and_(
                model_cls.enabled.is_(True),
                or_(
                    model_cls.last_test_status.is_(None),
                    model_cls.last_test_status != "failed",
                ),
            ),
            0,
        ),
        else_=1,
    )


def _sort_column(
    model_cls: type[GatewayModel] | type[SystemGatewayModel],
    sort_field: ModelListSortField,
) -> InstrumentedAttribute[Any]:
    if sort_field == ModelListSortField.CREATED_AT:
        return model_cls.created_at
    if sort_field == ModelListSortField.PROVIDER:
        return model_cls.provider
    if sort_field == ModelListSortField.LAST_TESTED_AT:
        return model_cls.last_tested_at
    return model_cls.name


def build_system_list_stmt(
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
) -> Select[tuple[SystemGatewayModel]]:
    clauses: list[ColumnElement[bool]] = []
    if only_enabled:
        clauses.append(SystemGatewayModel.enabled.is_(True))
    if enabled is not None:
        clauses.append(SystemGatewayModel.enabled.is_(enabled))
    if capability:
        clauses.append(SystemGatewayModel.capability == capability)
    if provider is not None:
        clauses.append(SystemGatewayModel.provider == provider)
    if credential_id is not None:
        clauses.append(SystemGatewayModel.credential_id == credential_id)
    search = _registry_q_clause(
        name_col=SystemGatewayModel.name,
        real_model_col=SystemGatewayModel.real_model,
        provider_col=SystemGatewayModel.provider,
        credential_id_col=SystemGatewayModel.credential_id,
        q=q,
        system_credential=True,
    )
    if search is not None:
        clauses.append(search)
    conn = _connectivity_clause(SystemGatewayModel.last_test_status, connectivity)
    if conn is not None:
        clauses.append(conn)

    sort_col = _sort_column(SystemGatewayModel, sort_field)
    ordering = [_availability_order(SystemGatewayModel), sort_col.asc()]
    if order == ModelListSortOrder.DESC:
        ordering = [_availability_order(SystemGatewayModel), sort_col.desc()]

    stmt = select(SystemGatewayModel)
    if clauses:
        stmt = stmt.where(*clauses)
    return stmt.order_by(*ordering)


def build_tenant_list_stmt(
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
    readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
    user_scope_owner_id: uuid.UUID | None = None,
) -> Select[tuple[GatewayModel]]:
    clauses: list[ColumnElement[bool]] = [GatewayModel.tenant_id == tenant_id]
    if only_enabled:
        clauses.append(GatewayModel.enabled.is_(True))
    if enabled is not None:
        clauses.append(GatewayModel.enabled.is_(enabled))
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
    search = _registry_q_clause(
        name_col=GatewayModel.name,
        real_model_col=GatewayModel.real_model,
        provider_col=GatewayModel.provider,
        credential_id_col=GatewayModel.credential_id,
        q=q,
        system_credential=False,
        readable_team_credential_ids=readable_team_credential_ids,
        user_scope_owner_id=user_scope_owner_id,
    )
    if search is not None:
        clauses.append(search)
    conn = _connectivity_clause(GatewayModel.last_test_status, connectivity)
    if conn is not None:
        clauses.append(conn)

    sort_col = _sort_column(GatewayModel, sort_field)
    ordering = [_availability_order(GatewayModel), sort_col.asc()]
    if order == ModelListSortOrder.DESC:
        ordering = [_availability_order(GatewayModel), sort_col.desc()]

    stmt = select(GatewayModel).where(*clauses)
    return stmt.order_by(*ordering)


def _tenant_registry_clauses(
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
    readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
) -> list[ColumnElement[bool]]:
    if not tenant_ids:
        return [GatewayModel.tenant_id.is_(None)]
    clauses: list[ColumnElement[bool]] = [GatewayModel.tenant_id.in_(tenant_ids)]
    if only_enabled:
        clauses.append(GatewayModel.enabled.is_(True))
    if enabled is not None:
        clauses.append(GatewayModel.enabled.is_(enabled))
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
    search = _registry_q_clause(
        name_col=GatewayModel.name,
        real_model_col=GatewayModel.real_model,
        provider_col=GatewayModel.provider,
        credential_id_col=GatewayModel.credential_id,
        q=q,
        system_credential=False,
        readable_team_credential_ids=readable_team_credential_ids,
    )
    if search is not None:
        clauses.append(search)
    conn = _connectivity_clause(GatewayModel.last_test_status, connectivity)
    if conn is not None:
        clauses.append(conn)
    return clauses


def build_tenants_list_stmt(
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
    readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
) -> Select[tuple[GatewayModel]]:
    clauses = _tenant_registry_clauses(
        tenant_ids=tenant_ids,
        only_enabled=only_enabled,
        capability=capability,
        provider=provider,
        credential_id=credential_id,
        exclude_user_scope_credentials=exclude_user_scope_credentials,
        enabled=enabled,
        q=q,
        connectivity=connectivity,
        readable_team_credential_ids=readable_team_credential_ids,
    )
    sort_col = _sort_column(GatewayModel, sort_field)
    ordering = [_availability_order(GatewayModel), sort_col.asc()]
    if order == ModelListSortOrder.DESC:
        ordering = [_availability_order(GatewayModel), sort_col.desc()]
    return select(GatewayModel).where(*clauses).order_by(*ordering)


async def list_tenant_ids_with_team_registry_for_tenants(
    session: AsyncSession,
    *,
    tenant_ids: list[uuid.UUID],
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
    if not tenant_ids:
        return []
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
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
        readable_team_credential_ids=readable_team_credential_ids,
    )
    subq = base.order_by(None).subquery()
    stmt = select(subq.c.tenant_id).distinct()
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def count_from_stmt(session: AsyncSession, stmt: Select[Any]) -> int:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    result = await session.execute(count_stmt)
    return int(result.scalar_one() or 0)


def _summary_select(
    *,
    enabled_col: ColumnElement[Any],
    status_col: ColumnElement[Any],
) -> Select[Any]:
    """聚合可用数；available 判定与 ``is_registry_connectivity_available`` 一致。"""
    available_expr = case(
        (
            and_(
                enabled_col.is_(True),
                or_(
                    status_col.is_(None),
                    status_col != "failed",
                ),
            ),
            1,
        ),
        else_=0,
    )
    return select(
        func.count().label("total"),
        func.sum(available_expr).label("available"),
        func.sum(case((status_col == "success", 1), else_=0)).label("success"),
        func.sum(case((status_col == "failed", 1), else_=0)).label("failed"),
        func.sum(case((status_col.is_(None), 1), else_=0)).label("unknown"),
    )


async def summarize_system_list(
    session: AsyncSession,
    *,
    only_enabled: bool,
    capability: str | None,
    provider: str | None,
    credential_id: uuid.UUID | None,
    enabled: bool | None,
    q: str | None,
) -> dict[str, int]:
    base = build_system_list_stmt(
        only_enabled=only_enabled,
        capability=capability,
        provider=provider,
        credential_id=credential_id,
        enabled=enabled,
        q=q,
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
    )
    subq = base.order_by(None).subquery()
    summary_stmt = _summary_select(
        enabled_col=subq.c.enabled,
        status_col=subq.c.last_test_status,
    ).select_from(subq)
    row = (await session.execute(summary_stmt)).one()
    total = int(row.total or 0)
    available = int(row.available or 0)
    return {
        "total": total,
        "available": available,
        "unavailable": total - available,
        "success": int(row.success or 0),
        "failed": int(row.failed or 0),
        "unknown": int(row.unknown or 0),
    }


async def summarize_tenant_list(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    only_enabled: bool,
    capability: str | None,
    provider: str | None,
    credential_id: uuid.UUID | None,
    exclude_user_scope_credentials: bool,
    enabled: bool | None,
    q: str | None,
    readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
    user_scope_owner_id: uuid.UUID | None = None,
) -> dict[str, int]:
    base = build_tenant_list_stmt(
        tenant_id=tenant_id,
        only_enabled=only_enabled,
        capability=capability,
        provider=provider,
        credential_id=credential_id,
        exclude_user_scope_credentials=exclude_user_scope_credentials,
        enabled=enabled,
        q=q,
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
        readable_team_credential_ids=readable_team_credential_ids,
        user_scope_owner_id=user_scope_owner_id,
    )
    subq = base.order_by(None).subquery()
    summary_stmt = _summary_select(
        enabled_col=subq.c.enabled,
        status_col=subq.c.last_test_status,
    ).select_from(subq)
    row = (await session.execute(summary_stmt)).one()
    total = int(row.total or 0)
    available = int(row.available or 0)
    return {
        "total": total,
        "available": available,
        "unavailable": total - available,
        "success": int(row.success or 0),
        "failed": int(row.failed or 0),
        "unknown": int(row.unknown or 0),
    }


async def summarize_tenants_list(
    session: AsyncSession,
    *,
    tenant_ids: list[uuid.UUID],
    only_enabled: bool,
    capability: str | None,
    provider: str | None,
    credential_id: uuid.UUID | None,
    exclude_user_scope_credentials: bool,
    enabled: bool | None,
    q: str | None,
    readable_team_credential_ids: Sequence[uuid.UUID] | None = None,
) -> dict[str, int]:
    base = build_tenants_list_stmt(
        tenant_ids=tenant_ids,
        only_enabled=only_enabled,
        capability=capability,
        provider=provider,
        credential_id=credential_id,
        exclude_user_scope_credentials=exclude_user_scope_credentials,
        enabled=enabled,
        q=q,
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
        readable_team_credential_ids=readable_team_credential_ids,
    )
    subq = base.order_by(None).subquery()
    summary_stmt = _summary_select(
        enabled_col=subq.c.enabled,
        status_col=subq.c.last_test_status,
    ).select_from(subq)
    row = (await session.execute(summary_stmt)).one()
    total = int(row.total or 0)
    available = int(row.available or 0)
    return {
        "total": total,
        "available": available,
        "unavailable": total - available,
        "success": int(row.success or 0),
        "failed": int(row.failed or 0),
        "unknown": int(row.unknown or 0),
    }


__all__ = [
    "build_system_list_stmt",
    "build_tenant_list_stmt",
    "build_tenants_list_stmt",
    "count_from_stmt",
    "list_tenant_ids_with_team_registry_for_tenants",
    "summarize_system_list",
    "summarize_tenant_list",
    "summarize_tenants_list",
]
