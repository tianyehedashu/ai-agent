"""跨团队可管理凭据聚合读侧（actor 维度）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.management.credential_read_mappers import credential_from_orm
from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.domain.policies.managed_team_credentials_policy import WritableTeamSnapshot
from domains.gateway.domain.policies.managed_team_resource_policy import (
    build_managed_team_readable_resource_list_plan,
)
from domains.gateway.domain.team_credential_access import (
    filter_team_credentials_visible_to_actor,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.tenancy.application.ports import GatewayTeamListingPort
from domains.tenancy.application.team_service import TeamService
from libs.api.pagination import PageParams, build_page

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from libs.api.pagination import PaginatedListResponse


@dataclass(frozen=True)
class ManagedTeamCredentialListPage:
    page: PaginatedListResponse[CredentialReadModel]
    queried_team_count: int
    queried_personal_team_count: int
    queried_shared_team_count: int
    tenant_ids_with_credentials: tuple[uuid.UUID, ...]


async def list_managed_team_credentials_for_actor(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    page_params: PageParams,
    search: str | None,
    encryption_key: str | None,
    team_listing: GatewayTeamListingPort | None = None,
) -> ManagedTeamCredentialListPage:
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
    cred_repo = ProviderCredentialRepository(session)

    all_rows = await cred_repo.list_team_scope_for_tenants_page(
        tenant_ids,
        offset=0,
        limit=100_000,
    )
    visible_rows = []
    visible_tenant_ids: set[uuid.UUID] = set()
    for row in all_rows:
        if row.tenant_id is None:
            continue
        team_role = role_by_tenant.get(row.tenant_id, "member")
        visible = filter_team_credentials_visible_to_actor(
            [row],
            actor_user_id=user_id,
            team_role=team_role,
            is_platform_admin=False,
        )
        if visible:
            visible_rows.append(row)
            visible_tenant_ids.add(row.tenant_id)

    total = len(visible_rows)
    page_rows = visible_rows[
        page_params.offset : page_params.offset + page_params.page_size
    ]
    items = [credential_from_orm(row, encryption_key=encryption_key) for row in page_rows]
    page = build_page(
        items=items,
        total=total,
        page=page_params.page,
        page_size=page_params.page_size,
    )
    return ManagedTeamCredentialListPage(
        page=page,
        queried_team_count=plan.queried_team_count,
        queried_personal_team_count=plan.queried_personal_team_count,
        queried_shared_team_count=plan.queried_shared_team_count,
        tenant_ids_with_credentials=tuple(sorted(visible_tenant_ids)),
    )


__all__ = [
    "ManagedTeamCredentialListPage",
    "list_managed_team_credentials_for_actor",
]
