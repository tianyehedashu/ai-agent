"""Router model_name 编解码。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.router_model_name import (
    decode_router_model_name,
    deployment_scope_team_id,
    encode_router_model_name,
    router_deployment_row_id,
)


def test_encode_team_and_system() -> None:
    team = uuid.uuid4()
    assert encode_router_model_name(team, "gpt-4o") == f"gw/t/{team}/gpt-4o"
    assert encode_router_model_name(None, "gpt-4o") == "gw/s/gpt-4o"


def test_deployment_scope_team_id() -> None:
    team = uuid.uuid4()
    assert deployment_scope_team_id(type("T", (), {"tenant_id": team})()) == team
    assert deployment_scope_team_id(type("S", (), {})()) is None


def test_decode_roundtrip() -> None:
    team = uuid.uuid4()
    encoded = encode_router_model_name(team, "my-model")
    decoded = decode_router_model_name(encoded)
    assert decoded == (team, "my-model")
    assert decode_router_model_name("gw/s/foo") == (None, "foo")
    assert decode_router_model_name("plain-name") is None


def test_router_deployment_row_id_stable_and_unique() -> None:
    model_id = uuid.uuid4()
    name_a = f"gw/t/{uuid.uuid4()}/alias"
    name_b = f"gw/t/{uuid.uuid4()}/alias"
    # 同一 GatewayModel 在不同 model_name 下派生出不同的行 id（避免 cooldown/统计串台）。
    assert router_deployment_row_id(name_a, model_id) != router_deployment_row_id(name_b, model_id)
    # 同 (model_name, model_id) 跨 reload 稳定，且与 GatewayModel.id 解耦。
    assert router_deployment_row_id(name_a, model_id) == router_deployment_row_id(name_a, model_id)
    assert router_deployment_row_id(name_a, model_id) != str(model_id)
    # 同一 model_name 下不同 GatewayModel 也彼此唯一。
    assert router_deployment_row_id(name_a, model_id) != router_deployment_row_id(
        name_a, uuid.uuid4()
    )
