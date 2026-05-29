"""跨团队模型列表：凭据筛选下拉（来自注册模型绑定，非凭据 reveal）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.policies.managed_team_credentials_policy import WritableTeamSnapshot
from domains.gateway.domain.policies.managed_team_resource_policy import (
    build_managed_team_readable_resource_list_plan,
)
from domains.gateway.domain.team_registry_credential_display import (
    TeamRegistryCredentialDisplay,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.tenancy.application.ports import GatewayTeamListingPort
from domains.tenancy.application.team_service import TeamService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ManagedTeamModelCredentialFilterList:
    items: tuple[TeamRegistryCredentialDisplay, ...]
    queried_team_count: int


async def list_managed_team_model_credential_filters_for_actor(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    is_platform_admin: bool,
    team_listing: GatewayTeamListingPort | None = None,
) -> ManagedTeamModelCredentialFilterList:
    listing = team_listing or TeamService(session)
    memberships = await listing.list_gateway_team_memberships(
        user_id,
        is_platform_admin=is_platform_admin,
    )
    snapshots = [
        WritableTeamSnapshot(team_id=m.team_id, kind=m.kind, role=m.role) for m in memberships
    ]
    plan = build_managed_team_readable_resource_list_plan(
        snapshots,
        is_platform_admin=is_platform_admin,
    )
    tenant_ids = list(plan.tenant_ids)
    rows = await ProviderCredentialRepository(session).list_distinct_for_team_registry_in_tenants(
        tenant_ids
    )
    return ManagedTeamModelCredentialFilterList(
        items=tuple(rows),
        queried_team_count=plan.queried_team_count,
    )


__all__ = [
    "ManagedTeamModelCredentialFilterList",
    "list_managed_team_model_credential_filters_for_actor",
]
