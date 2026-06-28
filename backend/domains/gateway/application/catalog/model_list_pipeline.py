"""Gateway 模型列表查询 DTO 与分页管道。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.quota.entitlement_model_status import is_connectivity_requestable
from domains.gateway.domain.catalog.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
    matches_connectivity_filter,
    matches_search,
    sort_registry_rows,
    summarize_connectivity,
)
from domains.gateway.domain.catalog.model_registry_scope import (
    RegistryScope,
    exclude_user_scope_credentials_for_registry,
    filter_system_registry_rows,
    is_requestable_registry_scope,
    uses_merged_registry_list,
)
from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row
from domains.gateway.domain.catalog.registry_model_types import (
    ability_filters_via_sql_capability_column,
    registry_row_matches_ability_filter,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel
from domains.gateway.infrastructure.repositories.model_list_read_repository import (
    ModelListReadRepository,
)
from domains.gateway.infrastructure.repositories.model_list_sql import (
    build_system_list_stmt,
    build_tenant_list_stmt,
    build_tenants_list_stmt,
)
from libs.api.pagination import MAX_PAGE_SIZE, PageParams, slice_page, total_pages

from .gateway_model_listing import list_merged_models_for_tenant
from .model_credential_enrichment import (
    build_credential_name_map_for_models,
)
from .model_list_readable_credentials import (
    readable_team_credential_ids_for_tenant,
    readable_team_credential_ids_for_tenants,
    readable_user_credential_ids,
)

GatewayRegistryModelRow = GatewayModel | SystemGatewayModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_MODEL_LIST_IDS_LIMIT = 5000


@dataclass(frozen=True, slots=True)
class ModelListQuery:
    page_params: PageParams
    q: str | None = None
    connectivity: ModelListConnectivityFilter = ModelListConnectivityFilter.ALL
    sort: ModelListSortField = ModelListSortField.NAME
    order: ModelListSortOrder = ModelListSortOrder.ASC
    provider: str | None = None
    credential_id: uuid.UUID | None = None
    ability: str | None = None
    capability: str | None = None  # deprecated：列表筛选用 ability；未设 ability 时作回退
    enabled: bool | None = None


@dataclass(frozen=True, slots=True)
class ModelListPageResult:
    items: list[GatewayRegistryModelRow]
    total: int
    page: int
    page_size: int
    connectivity_summary: dict[str, int]


@dataclass(frozen=True, slots=True)
class ModelListIdsResult:
    ids: list[uuid.UUID]
    truncated: bool


def resolved_registry_ability(query: ModelListQuery) -> str | None:
    """列表 ``?type=`` 优先；``?capability=`` 仅作兼容回退。"""
    if query.ability:
        return query.ability
    if query.capability:
        return query.capability
    return None


def sql_capability_for_registry_ability(ability: str | None) -> str | None:
    """可下推 SQL ``capability =`` 时返回筛选值，否则 None（改内存 policy）。"""
    if not ability:
        return None
    if ability_filters_via_sql_capability_column(ability):
        return ability
    return None


def _filter_rows_in_memory(
    rows: list[GatewayRegistryModelRow],
    query: ModelListQuery,
    *,
    credential_names: dict[uuid.UUID, str] | None = None,
) -> list[GatewayRegistryModelRow]:
    ability = resolved_registry_ability(query)
    filtered: list[GatewayRegistryModelRow] = []
    for row in rows:
        if query.enabled is not None and row.enabled is not query.enabled:
            continue
        if ability and not registry_row_matches_ability_filter(row, ability):
            continue
        if query.provider is not None and row.provider != query.provider:
            continue
        if query.credential_id is not None and row.credential_id != query.credential_id:
            continue
        if not matches_connectivity_filter(row.last_test_status, query.connectivity):
            continue
        cred_name = credential_names.get(row.credential_id) if credential_names else None
        if not matches_search(
            name=row.name,
            real_model=row.real_model,
            provider=row.provider,
            q=query.q,
            credential_name=cred_name,
        ):
            continue
        filtered.append(row)
    return filtered


async def _credential_names_for_search(
    session: AsyncSession,
    rows: list[GatewayRegistryModelRow],
    q: str | None,
    *,
    readable_credential_ids: frozenset[uuid.UUID] | None = None,
) -> dict[uuid.UUID, str] | None:
    if not q or not q.strip():
        return None
    names = await build_credential_name_map_for_models(session, rows)
    if readable_credential_ids is None:
        return names
    return {cid: label for cid, label in names.items() if cid in readable_credential_ids}


async def _list_system_page(
    repo: ModelListReadRepository,
    query: ModelListQuery,
    *,
    only_enabled: bool,
) -> ModelListPageResult:
    ability = resolved_registry_ability(query)
    sql_cap = sql_capability_for_registry_ability(ability)
    if ability and not sql_cap:
        stmt = build_system_list_stmt(
            only_enabled=only_enabled,
            capability=None,
            provider=query.provider,
            credential_id=query.credential_id,
            enabled=query.enabled,
            q=query.q,
            connectivity=query.connectivity,
            sort_field=query.sort,
            order=query.order,
        )
        result = await repo._session.execute(stmt)
        all_rows = list(result.scalars().all())
        cred_names = await _credential_names_for_search(repo._session, all_rows, query.q)
        filtered = _filter_rows_in_memory(all_rows, query, credential_names=cred_names)
        summary = summarize_connectivity(filtered)
        sorted_rows = sort_registry_rows(
            filtered,
            sort_field=query.sort,
            order=query.order,
        )
        page_items, total = slice_page(
            sorted_rows,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
        )
        return ModelListPageResult(
            items=page_items,
            total=total,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
            connectivity_summary=summary,
        )
    items, total, summary = await repo.paginate_system(
        only_enabled=only_enabled,
        capability=sql_cap,
        provider=query.provider,
        credential_id=query.credential_id,
        enabled=query.enabled,
        q=query.q,
        connectivity=query.connectivity,
        sort_field=query.sort,
        order=query.order,
        offset=query.page_params.offset,
        limit=query.page_params.page_size,
    )
    return ModelListPageResult(
        items=items,
        total=total,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
        connectivity_summary=summary,
    )


async def _list_tenant_page(
    repo: ModelListReadRepository,
    query: ModelListQuery,
    *,
    tenant_id: uuid.UUID,
    only_enabled: bool,
    exclude_user_scope_credentials: bool,
    actor_user_id: uuid.UUID | None = None,
    team_role: str = "member",
    is_platform_admin: bool = False,
    user_scope_owner_id: uuid.UUID | None = None,
) -> ModelListPageResult:
    readable_team_ids: frozenset[uuid.UUID] | None = None
    if query.q and query.q.strip():
        if user_scope_owner_id is not None:
            readable_team_ids = await readable_user_credential_ids(
                repo._session, user_scope_owner_id
            )
        elif actor_user_id is not None:
            readable_team_ids = await readable_team_credential_ids_for_tenant(
                repo._session,
                tenant_id,
                actor_user_id=actor_user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
    ability = resolved_registry_ability(query)
    sql_cap = sql_capability_for_registry_ability(ability)
    if ability and not sql_cap:
        stmt = build_tenant_list_stmt(
            tenant_id=tenant_id,
            only_enabled=only_enabled,
            capability=None,
            provider=query.provider,
            credential_id=query.credential_id,
            exclude_user_scope_credentials=exclude_user_scope_credentials,
            enabled=query.enabled,
            q=query.q,
            connectivity=query.connectivity,
            sort_field=query.sort,
            order=query.order,
            readable_team_credential_ids=(
                None if user_scope_owner_id is not None else readable_team_ids
            ),
            user_scope_owner_id=user_scope_owner_id,
        )
        result = await repo._session.execute(stmt)
        all_rows = list(result.scalars().all())
        cred_names = await _credential_names_for_search(
            repo._session,
            all_rows,
            query.q,
            readable_credential_ids=readable_team_ids,
        )
        filtered = _filter_rows_in_memory(all_rows, query, credential_names=cred_names)
        summary = summarize_connectivity(filtered)
        sorted_rows = sort_registry_rows(
            filtered,
            sort_field=query.sort,
            order=query.order,
        )
        page_items, total = slice_page(
            sorted_rows,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
        )
        return ModelListPageResult(
            items=page_items,
            total=total,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
            connectivity_summary=summary,
        )
    items, total, summary = await repo.paginate_tenant(
        tenant_id=tenant_id,
        only_enabled=only_enabled,
        exclude_user_scope_credentials=exclude_user_scope_credentials,
        capability=sql_cap,
        provider=query.provider,
        credential_id=query.credential_id,
        enabled=query.enabled,
        q=query.q,
        connectivity=query.connectivity,
        sort_field=query.sort,
        order=query.order,
        offset=query.page_params.offset,
        limit=query.page_params.page_size,
        readable_team_credential_ids=(
            None if user_scope_owner_id is not None else readable_team_ids
        ),
        user_scope_owner_id=user_scope_owner_id,
    )
    return ModelListPageResult(
        items=items,
        total=total,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
        connectivity_summary=summary,
    )


async def list_gateway_models_for_tenants_page(
    session: AsyncSession,
    tenant_ids: list[uuid.UUID],
    query: ModelListQuery,
    *,
    only_enabled: bool = False,
    exclude_user_scope_credentials: bool = True,
    actor_user_id: uuid.UUID | None = None,
    role_by_tenant: dict[uuid.UUID, str] | None = None,
    is_platform_admin: bool = False,
    readable_team_credential_ids: frozenset[uuid.UUID] | None = None,
) -> ModelListPageResult:
    """跨 tenant 聚合 team registry 模型分页（managed-team-models 读侧）。"""
    repo = ModelListReadRepository(session)
    if not tenant_ids:
        return ModelListPageResult(
            items=[],
            total=0,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
            connectivity_summary=summarize_connectivity([]),
        )
    readable_team_ids = readable_team_credential_ids
    if (
        readable_team_ids is None
        and query.q
        and query.q.strip()
        and actor_user_id is not None
        and role_by_tenant is not None
    ):
        readable_team_ids = await readable_team_credential_ids_for_tenants(
            session,
            tenant_ids,
            actor_user_id=actor_user_id,
            role_by_tenant=role_by_tenant,
            is_platform_admin=is_platform_admin,
        )
    ability = resolved_registry_ability(query)
    sql_cap = sql_capability_for_registry_ability(ability)
    if ability and not sql_cap:
        stmt = build_tenants_list_stmt(
            tenant_ids=tenant_ids,
            only_enabled=only_enabled,
            capability=None,
            provider=query.provider,
            credential_id=query.credential_id,
            exclude_user_scope_credentials=exclude_user_scope_credentials,
            enabled=query.enabled,
            q=query.q,
            connectivity=query.connectivity,
            sort_field=query.sort,
            order=query.order,
            readable_team_credential_ids=readable_team_ids,
        )
        result = await session.execute(stmt)
        all_rows = list(result.scalars().all())
        cred_names = await _credential_names_for_search(
            session,
            all_rows,
            query.q,
            readable_credential_ids=readable_team_ids,
        )
        filtered = _filter_rows_in_memory(all_rows, query, credential_names=cred_names)
        summary = summarize_connectivity(filtered)
        sorted_rows = sort_registry_rows(
            filtered,
            sort_field=query.sort,
            order=query.order,
        )
        page_items, total = slice_page(
            sorted_rows,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
        )
        return ModelListPageResult(
            items=page_items,
            total=total,
            page=query.page_params.page,
            page_size=query.page_params.page_size,
            connectivity_summary=summary,
        )
    items, total, summary = await repo.paginate_tenants(
        tenant_ids=tenant_ids,
        only_enabled=only_enabled,
        exclude_user_scope_credentials=exclude_user_scope_credentials,
        capability=sql_cap,
        provider=query.provider,
        credential_id=query.credential_id,
        enabled=query.enabled,
        q=query.q,
        connectivity=query.connectivity,
        sort_field=query.sort,
        order=query.order,
        offset=query.page_params.offset,
        limit=query.page_params.page_size,
        readable_team_credential_ids=readable_team_ids,
    )
    return ModelListPageResult(
        items=items,
        total=total,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
        connectivity_summary=summary,
    )


async def _filter_merged_rows_deployable(
    session: AsyncSession,
    rows: list[GatewayRegistryModelRow],
) -> list[GatewayRegistryModelRow]:
    """批量过滤：仅保留凭据存在且 active 的模型行（与 Router 注册条件对齐）。"""
    if not rows:
        return []
    team_cred_ids: list[uuid.UUID] = []
    system_cred_ids: list[uuid.UUID] = []
    for row in rows:
        if registry_kind_for_merged_row(row) == "team":
            team_cred_ids.append(row.credential_id)
        else:
            system_cred_ids.append(row.credential_id)

    active_ids: set[uuid.UUID] = set()
    if team_cred_ids:
        from domains.gateway.infrastructure.repositories.credential_repository import (
            ProviderCredentialRepository,
        )

        creds = await ProviderCredentialRepository(session).list_by_ids(team_cred_ids)
        active_ids.update(c.id for c in creds if c.is_active)
    if system_cred_ids:
        from domains.gateway.infrastructure.repositories.system_credential_repository import (
            SystemProviderCredentialRepository,
        )

        creds = await SystemProviderCredentialRepository(session).list_by_ids(system_cred_ids)
        active_ids.update(c.id for c in creds if c.is_active)

    return [row for row in rows if row.credential_id in active_ids]


async def _list_merged_page(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query: ModelListQuery,
    *,
    registry_scope: RegistryScope,
    only_enabled: bool,
    user_id: uuid.UUID | None,
) -> ModelListPageResult:
    merged = await list_merged_models_for_tenant(
        session,
        tenant_id,
        only_enabled=True if is_requestable_registry_scope(registry_scope) else only_enabled,
        provider=query.provider,
        credential_id=query.credential_id,
        user_id=user_id,
        apply_visibility_filter=True,
    )
    if registry_scope == "system_requestable":
        merged = filter_system_registry_rows(merged)
    if is_requestable_registry_scope(registry_scope):
        merged = [row for row in merged if is_connectivity_requestable(row.last_test_status)]
    if uses_merged_registry_list(registry_scope):
        merged = await _filter_merged_rows_deployable(session, merged)
    summary_query = ModelListQuery(
        page_params=query.page_params,
        q=query.q,
        connectivity=ModelListConnectivityFilter.ALL,
        sort=query.sort,
        order=query.order,
        provider=query.provider,
        credential_id=query.credential_id,
        ability=query.ability,
        capability=query.capability,
        enabled=query.enabled,
    )
    cred_names = await _credential_names_for_search(session, merged, query.q)
    summary_rows = _filter_rows_in_memory(merged, summary_query, credential_names=cred_names)
    summary = summarize_connectivity(summary_rows)
    filtered = _filter_rows_in_memory(merged, query, credential_names=cred_names)
    sorted_rows = sort_registry_rows(
        filtered,
        sort_field=query.sort,
        order=query.order,
    )
    page_items, total = slice_page(
        sorted_rows,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
    )
    return ModelListPageResult(
        items=page_items,
        total=total,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
        connectivity_summary=summary,
    )


async def list_gateway_models_page(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query: ModelListQuery,
    *,
    registry_scope: RegistryScope = "team",
    only_enabled: bool = False,
    user_id: uuid.UUID | None = None,
    team_role: str = "member",
    is_platform_admin: bool = False,
) -> ModelListPageResult:
    repo = ModelListReadRepository(session)
    if registry_scope == "team":
        return await _list_tenant_page(
            repo,
            query,
            tenant_id=tenant_id,
            only_enabled=only_enabled,
            exclude_user_scope_credentials=exclude_user_scope_credentials_for_registry(
                registry_scope
            ),
            actor_user_id=user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
    if registry_scope == "system":
        return await _list_system_page(repo, query, only_enabled=only_enabled)
    if uses_merged_registry_list(registry_scope):
        return await _list_merged_page(
            session,
            tenant_id,
            query,
            registry_scope=registry_scope,
            only_enabled=only_enabled,
            user_id=user_id,
        )
    raise ValueError(f"unsupported registry_scope: {registry_scope}")


async def list_personal_models_page(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query: ModelListQuery,
    *,
    user_id: uuid.UUID | None = None,
) -> ModelListPageResult:
    repo = ModelListReadRepository(session)
    return await _list_tenant_page(
        repo,
        query,
        tenant_id=tenant_id,
        only_enabled=False,
        exclude_user_scope_credentials=False,
        user_scope_owner_id=user_id,
    )


async def list_gateway_model_ids(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    query: ModelListQuery,
    *,
    registry_scope: RegistryScope = "team",
    only_enabled: bool = False,
    user_id: uuid.UUID | None = None,
    team_role: str = "member",
    is_platform_admin: bool = False,
    max_ids: int = DEFAULT_MODEL_LIST_IDS_LIMIT,
) -> ModelListIdsResult:
    """同 filter 不分页，供批量探活/删除收集 id；超过 max_ids 时 truncated=True。"""
    base_kwargs = {
        "q": query.q,
        "connectivity": query.connectivity,
        "sort": query.sort,
        "order": query.order,
        "provider": query.provider,
        "credential_id": query.credential_id,
        "ability": query.ability,
        "capability": query.capability,
        "enabled": query.enabled,
    }
    if registry_scope in ("team", "system"):
        collected: list[uuid.UUID] = []
        page_num = 1
        total = 0
        while len(collected) < max_ids:
            page_query = ModelListQuery(
                page_params=PageParams(page=page_num, page_size=MAX_PAGE_SIZE),
                **base_kwargs,
            )
            page = await list_gateway_models_page(
                session,
                tenant_id,
                page_query,
                registry_scope=registry_scope,
                only_enabled=only_enabled,
                user_id=user_id,
                team_role=team_role,
                is_platform_admin=is_platform_admin,
            )
            total = page.total
            for row in page.items:
                collected.append(row.id)
                if len(collected) >= max_ids:
                    break
            pages = total_pages(total, MAX_PAGE_SIZE)
            if page_num >= pages:
                break
            page_num += 1
        truncated = total > max_ids
        return ModelListIdsResult(ids=collected[:max_ids], truncated=truncated)

    merged = await list_merged_models_for_tenant(
        session,
        tenant_id,
        only_enabled=True if is_requestable_registry_scope(registry_scope) else only_enabled,
        provider=query.provider,
        credential_id=query.credential_id,
        user_id=user_id,
        apply_visibility_filter=True,
    )
    if registry_scope == "system_requestable":
        merged = filter_system_registry_rows(merged)
    if is_requestable_registry_scope(registry_scope):
        merged = [row for row in merged if is_connectivity_requestable(row.last_test_status)]
    cred_names = await _credential_names_for_search(session, merged, query.q)
    filtered = _filter_rows_in_memory(merged, query, credential_names=cred_names)
    sorted_rows = sort_registry_rows(filtered, sort_field=query.sort, order=query.order)
    ids = [row.id for row in sorted_rows[:max_ids]]
    return ModelListIdsResult(ids=ids, truncated=len(sorted_rows) > max_ids)


__all__ = [
    "DEFAULT_MODEL_LIST_IDS_LIMIT",
    "ModelListIdsResult",
    "ModelListPageResult",
    "ModelListQuery",
    "list_gateway_model_ids",
    "list_gateway_models_for_tenants_page",
    "list_gateway_models_page",
    "list_personal_models_page",
    "resolved_registry_ability",
    "sql_capability_for_registry_ability",
]
