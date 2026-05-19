"""Router model_name 编解码。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.router_model_name import (
    decode_router_model_name,
    encode_router_model_name,
)


def test_encode_team_and_system() -> None:
    team = uuid.uuid4()
    assert encode_router_model_name(team, "gpt-4o") == f"gw/t/{team}/gpt-4o"
    assert encode_router_model_name(None, "gpt-4o") == "gw/s/gpt-4o"


def test_decode_roundtrip() -> None:
    team = uuid.uuid4()
    encoded = encode_router_model_name(team, "my-model")
    decoded = decode_router_model_name(encoded)
    assert decoded == (team, "my-model")
    assert decode_router_model_name("gw/s/foo") == (None, "foo")
    assert decode_router_model_name("plain-name") is None
