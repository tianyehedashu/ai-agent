"""GatewayRoute / SystemGatewayRoute ORM → API 投影 dict。"""

from __future__ import annotations

from typing import Any

from domains.gateway.application.management.orm_row_projection import tenant_scoped_orm_dict
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute


def route_row_to_api_dict(
    record: GatewayRoute | SystemGatewayRoute,
    *,
    owner_team_kind: str | None = None,
) -> dict[str, Any]:
    data = tenant_scoped_orm_dict(record)
    if isinstance(record, SystemGatewayRoute):
        data["team_id"] = None
        data["tenant_id"] = None
        data["source"] = "system"
        data["owner_team_kind"] = "system"
    else:
        data["source"] = "team"
        data["owner_team_kind"] = owner_team_kind
    return data


__all__ = ["route_row_to_api_dict"]
