"""route_read_mappers 单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import uuid

from domains.gateway.application.management.route_read_mappers import route_row_to_api_dict
from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayRoute


def test_route_row_to_api_dict_injects_owner_team_kind_for_team_route() -> None:
    tenant_id = uuid.uuid4()
    record = MagicMock(spec=GatewayRoute)

    with patch(
        "domains.gateway.application.management.route_read_mappers.tenant_scoped_orm_dict",
        return_value={"tenant_id": tenant_id, "team_id": tenant_id},
    ):
        data = route_row_to_api_dict(record, owner_team_kind="personal")

    assert data["source"] == "team"
    assert data["owner_team_kind"] == "personal"


def test_route_row_to_api_dict_system_route_sets_owner_team_kind_system() -> None:
    record = MagicMock(spec=SystemGatewayRoute)

    with patch(
        "domains.gateway.application.management.route_read_mappers.tenant_scoped_orm_dict",
        return_value={"tenant_id": uuid.uuid4()},
    ):
        data = route_row_to_api_dict(record)

    assert data["source"] == "system"
    assert data["owner_team_kind"] == "system"
    assert data["team_id"] is None
    assert data["tenant_id"] is None
