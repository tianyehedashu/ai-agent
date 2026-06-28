"""GatewayVirtualKeyTeamGrant → grants API Schema。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.presentation.schemas.grants import (
    GrantableTeamResponse,
    VirtualKeyTeamGrantResponse,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from domains.gateway.infrastructure.models.virtual_key_team_grant import (
        GatewayVirtualKeyTeamGrant,
    )


def grants_to_responses(
    grants: Sequence[GatewayVirtualKeyTeamGrant],
    *,
    team_map: dict[uuid.UUID, tuple[str, str]],
    model_counts: dict[uuid.UUID, int],
    model_names: dict[uuid.UUID, list[str]],
) -> list[VirtualKeyTeamGrantResponse]:
    return [
        VirtualKeyTeamGrantResponse(
            id=g.id,
            vkey_id=g.vkey_id,
            tenant_id=g.tenant_id,
            is_self=g.is_self,
            created_at=g.created_at,
            revoked_at=g.revoked_at,
            granted_team_name=team_map.get(g.tenant_id, ("", ""))[0] or None,
            granted_team_slug=team_map.get(g.tenant_id, ("", ""))[1] or None,
            model_count=model_counts.get(g.tenant_id, 0),
            registered_model_names=model_names.get(g.tenant_id, []),
        )
        for g in grants
    ]


def grantable_teams_to_responses(
    rows: Sequence[tuple[uuid.UUID, str, str]],
    *,
    model_counts: dict[uuid.UUID, int],
) -> list[GrantableTeamResponse]:
    return [
        GrantableTeamResponse(
            team_id=team_id,
            name=name,
            slug=slug,
            model_count=model_counts.get(team_id, 0),
        )
        for team_id, name, slug in rows
    ]


__all__ = ["grantable_teams_to_responses", "grants_to_responses"]
