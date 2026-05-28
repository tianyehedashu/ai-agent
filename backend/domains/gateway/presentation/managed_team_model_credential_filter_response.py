"""跨团队模型凭据筛选下拉 → API Schema。"""

from __future__ import annotations

from domains.gateway.application.management.managed_team_model_credential_filter_reads import (
    ManagedTeamModelCredentialFilterList,
)
from domains.gateway.infrastructure.repositories.credential_repository import (
    TeamRegistryCredentialDisplay,
)
from domains.gateway.presentation.schemas.common import (
    ManagedTeamModelCredentialFilterItem,
    ManagedTeamModelCredentialFilterListResponse,
)


def managed_team_model_credential_filter_item(
    row: TeamRegistryCredentialDisplay,
) -> ManagedTeamModelCredentialFilterItem:
    return ManagedTeamModelCredentialFilterItem(
        id=row.id,
        name=row.name,
        provider=row.provider,
        tenant_id=row.tenant_id,
    )


def build_managed_team_model_credential_filter_list_response(
    result: ManagedTeamModelCredentialFilterList,
) -> ManagedTeamModelCredentialFilterListResponse:
    return ManagedTeamModelCredentialFilterListResponse(
        items=[managed_team_model_credential_filter_item(row) for row in result.items],
        queried_team_count=result.queried_team_count,
    )


__all__ = [
    "build_managed_team_model_credential_filter_list_response",
    "managed_team_model_credential_filter_item",
]
