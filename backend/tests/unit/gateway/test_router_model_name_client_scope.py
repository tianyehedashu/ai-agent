"""代理层 Router model_name 编码须与 router_singleton deployment 作用域一致。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

from domains.gateway.application.catalog.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.route.router_model_name import router_model_name_for_client
from domains.gateway.domain.route.router_model_name import encode_router_model_name


def test_system_model_encodes_gw_s_not_gw_t() -> None:
    team = uuid.uuid4()
    record = SimpleNamespace(name="zai/glm-4-flash")  # 无 tenant_id → 系统级
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    encoded = router_model_name_for_client(team, "zai/glm-4-flash", resolved)
    assert encoded == "gw/s/zai/glm-4-flash"
    assert encoded == encode_router_model_name(None, "zai/glm-4-flash")


def test_tenant_model_encodes_gw_t() -> None:
    team = uuid.uuid4()
    record = SimpleNamespace(name="my-alias", tenant_id=team)
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    encoded = router_model_name_for_client(uuid.uuid4(), "my-alias", resolved)
    assert encoded == f"gw/t/{team}/my-alias"


def test_system_route_encodes_gw_s() -> None:
    team = uuid.uuid4()
    route = SimpleNamespace(virtual_model="smart-route")  # 系统路由无 tenant_id
    record = SimpleNamespace(name="gpt-4o", tenant_id=None)
    resolved = ResolvedModelName(record=record, route=route, via_route="smart-route")
    encoded = router_model_name_for_client(team, "smart-route", resolved)
    assert encoded == "gw/s/smart-route"
