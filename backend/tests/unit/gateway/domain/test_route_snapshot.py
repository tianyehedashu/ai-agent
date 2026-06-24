"""``route_snapshot`` — 请求日志路由快照字段。"""

from __future__ import annotations

from types import SimpleNamespace

from domains.gateway.domain.route_snapshot import build_route_snapshot_metadata


def test_build_route_snapshot_metadata_includes_fallbacks_and_retry_policy() -> None:
    route = SimpleNamespace(
        virtual_model="vm1",
        primary_models=["p1", "p2"],
        fallbacks_general=["fb1"],
        fallbacks_content_policy=["fb2"],
        fallbacks_context_window=[],
        strategy="simple-shuffle",
        retry_policy={"retries": 3},
    )
    snap = build_route_snapshot_metadata(route)
    assert snap == {
        "virtual_model": "vm1",
        "primary_models": ["p1", "p2"],
        "fallbacks_general": ["fb1"],
        "fallbacks_content_policy": ["fb2"],
        "fallbacks_context_window": [],
        "strategy": "simple-shuffle",
        "retry_policy": {"retries": 3},
    }


def test_build_route_snapshot_metadata_empty_retry_policy_is_none() -> None:
    route = SimpleNamespace(
        virtual_model="vm1",
        primary_models=[],
        fallbacks_general=None,
        fallbacks_content_policy=None,
        fallbacks_context_window=None,
        strategy="fallback",
        retry_policy=None,
    )
    snap = build_route_snapshot_metadata(route)
    assert snap["retry_policy"] is None
    assert snap["fallbacks_general"] == []
