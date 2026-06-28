"""个人虚拟路由可选 callable 模型聚合读侧。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal
import uuid

from domains.gateway.application.catalog.gateway_model_listing import list_merged_models_for_tenant
from domains.gateway.application.catalog.management.gateway_model_read_mappers import (
    gateway_model_row_to_api_dict,
)
from domains.gateway.application.catalog.model_list_pipeline import (
    ModelListQuery,
    _credential_names_for_search,
    _filter_merged_rows_deployable,
    _filter_rows_in_memory,
)
from domains.gateway.application.vkey.vkey_team_resolution import fetch_grant_team_slug_rows
from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row
from domains.gateway.domain.credential.managed_team_credentials_policy import WritableTeamSnapshot
from domains.gateway.domain.route.route_model_ref import (
    encode_route_model_ref,
    route_ref_prefix_dispatchable,
)
from domains.gateway.domain.visibility.managed_team_resource_policy import (
    build_managed_team_readable_resource_list_plan,
)
from domains.gateway.domain.vkey.vkey_grant_slug_policy import (
    build_slug_by_tenant_id,
    find_ambiguous_grant_slugs,
)
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from domains.tenancy.application.team_service import TeamService
from libs.api.pagination import slice_page

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel

    GatewayRegistryModelRow = GatewayModel | SystemGatewayModel
else:
    GatewayRegistryModelRow = object

TeamKind = Literal["personal", "shared", "system"]

_PRIORITY: dict[TeamKind, int] = {"personal": 0, "shared": 1, "system": 2}


@dataclass(frozen=True, slots=True)
class RouteCallableModelCandidate:
    route_ref: str
    team_kind: TeamKind
    tenant_id: uuid.UUID | None
    team_slug: str | None
    prefix_dispatchable: bool
    row: GatewayRegistryModelRow
    priority: int


@dataclass(frozen=True, slots=True)
class PersonalRouteCallableListPage:
    items: list[RouteCallableModelCandidate]
    total: int
    page: int
    page_size: int


def _team_kind_for_row(
    row: GatewayRegistryModelRow,
    *,
    personal_team_id: uuid.UUID,
) -> TeamKind:
    if registry_kind_for_merged_row(row) == "system":
        return "system"
    tenant_id = getattr(row, "tenant_id", None)
    if tenant_id == personal_team_id:
        return "personal"
    return "shared"


def _candidate_from_row(
    row: GatewayRegistryModelRow,
    *,
    personal_team_id: uuid.UUID,
    slug_by_tenant: dict[uuid.UUID, str],
    ambiguous_slugs: frozenset[str],
) -> RouteCallableModelCandidate | None:
    team_kind = _team_kind_for_row(row, personal_team_id=personal_team_id)
    tenant_id = getattr(row, "tenant_id", None)
    if team_kind == "system":
        tenant_id = None
    slug = slug_by_tenant.get(tenant_id) if tenant_id is not None else None
    prefix_ok = route_ref_prefix_dispatchable(
        route_owner_tenant_id=personal_team_id,
        model_tenant_id=tenant_id,
        slug=slug,
        ambiguous_slugs=ambiguous_slugs,
    )
    if not prefix_ok:
        return None
    try:
        route_ref = encode_route_model_ref(
            route_owner_tenant_id=personal_team_id,
            model_tenant_id=tenant_id,
            model_name=row.name,
            slug_by_tenant=slug_by_tenant,
            ambiguous_slugs=ambiguous_slugs,
        )
    except KeyError:
        return None
    return RouteCallableModelCandidate(
        route_ref=route_ref,
        team_kind=team_kind,
        tenant_id=tenant_id,
        team_slug=slug,
        prefix_dispatchable=True,
        row=row,
        priority=_PRIORITY[team_kind],
    )


async def collect_personal_route_callable_candidates(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
) -> list[RouteCallableModelCandidate]:
    """聚合 actor 可用于 personal 虚拟路由的全部 callable 模型候选。"""
    teams = TeamService(session)
    personal_team = await teams.ensure_personal_team(user_id)
    personal_id = personal_team.id
    memberships = await teams.list_gateway_team_memberships(
        user_id,
        is_platform_admin=is_platform_admin,
    )
    membership_ids = tuple(m.team_id for m in memberships)
    slug_rows = await fetch_grant_team_slug_rows(session, membership_ids)
    slug_by_tenant = build_slug_by_tenant_id(slug_rows)
    ambiguous = find_ambiguous_grant_slugs(slug_rows)

    snapshots = [
        WritableTeamSnapshot(team_id=m.team_id, kind=m.kind, role=m.role) for m in memberships
    ]
    plan = build_managed_team_readable_resource_list_plan(
        snapshots,
        is_platform_admin=is_platform_admin,
    )

    by_ref: dict[str, RouteCallableModelCandidate] = {}

    def upsert(candidate: RouteCallableModelCandidate) -> None:
        existing = by_ref.get(candidate.route_ref)
        if existing is None or candidate.priority < existing.priority:
            by_ref[candidate.route_ref] = candidate

    personal_merged = await list_merged_models_for_tenant(
        session,
        personal_id,
        only_enabled=True,
        user_id=user_id,
        apply_visibility_filter=True,
    )
    personal_deployable = await _filter_merged_rows_deployable(session, personal_merged)
    for row in personal_deployable:
        candidate = _candidate_from_row(
            row,
            personal_team_id=personal_id,
            slug_by_tenant=slug_by_tenant,
            ambiguous_slugs=ambiguous,
        )
        if candidate is not None:
            upsert(candidate)

    model_repo = GatewayModelRepository(session)
    for tenant_id in plan.tenant_ids:
        team_rows = await model_repo.list_tenant_owned(tenant_id, only_enabled=True)
        deployable = await _filter_merged_rows_deployable(session, team_rows)
        for row in deployable:
            candidate = _candidate_from_row(
                row,
                personal_team_id=personal_id,
                slug_by_tenant=slug_by_tenant,
                ambiguous_slugs=ambiguous,
            )
            if candidate is not None:
                upsert(candidate)

    return list(by_ref.values())


async def build_personal_route_allowed_refs(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
) -> frozenset[str]:
    candidates = await collect_personal_route_callable_candidates(
        session,
        user_id=user_id,
        is_platform_admin=is_platform_admin,
    )
    return frozenset(c.route_ref for c in candidates)


async def list_personal_route_owner_callable_pool(
    session: AsyncSession,
    *,
    owner_user_id: uuid.UUID,
) -> list[GatewayRegistryModelRow]:
    """个人路由 owner 可引用的全部 callable 模型行（含跨团队协作团队，去重）。"""
    candidates = await collect_personal_route_callable_candidates(
        session,
        user_id=owner_user_id,
        is_platform_admin=False,
    )
    seen: set[uuid.UUID] = set()
    pool: list[GatewayRegistryModelRow] = []
    for candidate in candidates:
        row_id = candidate.row.id
        if row_id in seen:
            continue
        seen.add(row_id)
        pool.append(candidate.row)
    return pool


async def list_personal_route_callable_models_for_actor(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    query: ModelListQuery,
    team_id: uuid.UUID | None = None,
) -> PersonalRouteCallableListPage:
    candidates = await collect_personal_route_callable_candidates(
        session,
        user_id=user_id,
        is_platform_admin=is_platform_admin,
    )
    if team_id is not None:
        candidates = [c for c in candidates if c.tenant_id == team_id or c.team_kind == "system"]
    rows = [c.row for c in candidates]
    cred_names = await _credential_names_for_search(session, rows, query.q)
    filtered_candidates = [
        c
        for c in candidates
        if c.row
        in _filter_rows_in_memory([c.row], query, credential_names=cred_names)
    ]
    sorted_candidates = sorted(
        filtered_candidates,
        key=lambda c: (
            c.route_ref.lower(),
            c.priority,
        ),
    )
    page_items, total = slice_page(
        sorted_candidates,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
    )
    return PersonalRouteCallableListPage(
        items=page_items,
        total=total,
        page=query.page_params.page,
        page_size=query.page_params.page_size,
    )


def route_callable_model_to_response_dict(candidate: RouteCallableModelCandidate) -> dict[str, object]:
    base = gateway_model_row_to_api_dict(candidate.row)
    base["route_ref"] = candidate.route_ref
    base["team_kind"] = candidate.team_kind
    base["team_slug"] = candidate.team_slug
    base["prefix_dispatchable"] = candidate.prefix_dispatchable
    return base


__all__ = [
    "PersonalRouteCallableListPage",
    "RouteCallableModelCandidate",
    "build_personal_route_allowed_refs",
    "collect_personal_route_callable_candidates",
    "list_personal_route_callable_models_for_actor",
    "list_personal_route_owner_callable_pool",
    "route_callable_model_to_response_dict",
]
