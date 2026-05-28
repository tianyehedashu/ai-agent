"""跨团队可管理模型聚合读侧（actor 维度）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.model_list_credential_assertions import (
    assert_managed_team_model_list_credential_filter,
)
from domains.gateway.application.model_list_pipeline import (
    ModelListPageResult,
    ModelListQuery,
    list_gateway_models_for_tenants_page,
    resolved_registry_ability,
    sql_capability_for_registry_ability,
)
from domains.gateway.application.model_list_readable_credentials import (
    readable_team_credential_ids_for_tenants,
)
from domains.gateway.domain.policies.managed_team_credentials_policy import WritableTeamSnapshot
from domains.gateway.domain.policies.managed_team_resource_policy import (
    build_managed_team_readable_resource_list_plan,
)
from domains.gateway.domain.policies.model_registry_scope import (
    exclude_user_scope_credentials_for_registry,
)
from domains.gateway.infrastructure.repositories.model_list_read_repository import (
    ModelListReadRepository,
)
from domains.tenancy.application.ports import GatewayTeamListingPort
from domains.tenancy.application.team_service import TeamService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ManagedTeamModelListPage:
    page: ModelListPageResult
    queried_team_count: int
    queried_personal_team_count: int
    queried_shared_team_count: int
    tenant_ids_with_models: tuple[uuid.UUID, ...]


async def list_managed_team_models_for_actor(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    query: ModelListQuery,
    search: str | None,
    team_listing: GatewayTeamListingPort | None = None,
) -> ManagedTeamModelListPage:
    listing = team_listing or TeamService(session)
    memberships = await listing.list_gateway_team_memberships(
        user_id,
        is_platform_admin=is_platform_admin,
        search=search,
    )
    snapshots = [
        WritableTeamSnapshot(team_id=m.team_id, kind=m.kind, role=m.role)
        for m in memberships
    ]
    plan = build_managed_team_readable_resource_list_plan(
        snapshots,
        is_platform_admin=is_platform_admin,
    )
    tenant_ids = list(plan.tenant_ids)
    role_by_tenant = {m.team_id: m.role for m in memberships if m.kind != "personal"}
    await assert_managed_team_model_list_credential_filter(
        session,
        query.credential_id,
        allowed_tenant_ids=tenant_ids,
    )
    exclude_user_scope = exclude_user_scope_credentials_for_registry("team")
    ability = resolved_registry_ability(query)
    sql_cap = sql_capability_for_registry_ability(ability)
    readable_team_ids: frozenset[uuid.UUID] | None = None
    if query.q and query.q.strip():
        readable_team_ids = await readable_team_credential_ids_for_tenants(
            session,
            tenant_ids,
            actor_user_id=user_id,
            role_by_tenant=role_by_tenant,
            is_platform_admin=is_platform_admin,
        )
    repo = ModelListReadRepository(session)
    tenant_ids_with_models = await repo.list_tenant_ids_with_team_registry(
        tenant_ids,
        exclude_user_scope_credentials=exclude_user_scope,
        capability=sql_cap,
        provider=query.provider,
        credential_id=query.credential_id,
        enabled=query.enabled,
        q=query.q,
        connectivity=query.connectivity,
        readable_team_credential_ids=readable_team_ids,
    )
    page = await list_gateway_models_for_tenants_page(
        session,
        tenant_ids,
        query,
        only_enabled=False,
        exclude_user_scope_credentials=exclude_user_scope,
        readable_team_credential_ids=readable_team_ids,
    )
    return ManagedTeamModelListPage(
        page=page,
        queried_team_count=plan.queried_team_count,
        queried_personal_team_count=plan.queried_personal_team_count,
        queried_shared_team_count=plan.queried_shared_team_count,
        tenant_ids_with_models=tuple(tenant_ids_with_models),
    )


__all__ = [
    "ManagedTeamModelListPage",
    "list_managed_team_models_for_actor",
]
