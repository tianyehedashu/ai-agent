"""``route_snapshot`` — 请求日志路由快照字段。"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

from domains.gateway.domain.route.route_snapshot import (
    build_delegated_route_snapshot_metadata,
    build_route_snapshot_metadata,
)


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


def test_build_delegated_route_snapshot_metadata_adds_owner_and_alias() -> None:
    owner_tenant = uuid.uuid4()
    owner_user = uuid.uuid4()
    route = SimpleNamespace(
        virtual_model="vm1",
        primary_models=["p1"],
        fallbacks_general=[],
        fallbacks_content_policy=[],
        fallbacks_context_window=[],
        strategy="simple-shuffle",
        retry_policy=None,
        tenant_id=owner_tenant,
        created_by_user_id=owner_user,
    )
    grant_id = uuid.uuid4()
    snap = build_delegated_route_snapshot_metadata(
        route,
        exposed_alias="exposed-x",
        owner_tenant_id=owner_tenant,
        owner_user_id=owner_user,
        route_grant_id=grant_id,
    )
    assert snap["delegated"] is True
    assert snap["route_grant_id"] == str(grant_id)
    assert snap["exposed_alias"] == "exposed-x"
    assert snap["owner_tenant_id"] == str(owner_tenant)
    assert snap["owner_user_id"] == str(owner_user)
    assert snap["primary_models"] == ["p1"]


def test_build_delegated_route_snapshot_metadata_nullable_owner_fields() -> None:
    route = SimpleNamespace(
        virtual_model="vm1",
        primary_models=[],
        fallbacks_general=[],
        fallbacks_content_policy=[],
        fallbacks_context_window=[],
        strategy="simple-shuffle",
        retry_policy=None,
        tenant_id=None,
        created_by_user_id=None,
    )
    snap = build_delegated_route_snapshot_metadata(
        route,
        exposed_alias=None,
        owner_tenant_id=None,
        owner_user_id=None,
        route_grant_id=None,
    )
    assert snap["owner_tenant_id"] is None
    assert snap["owner_user_id"] is None
    assert snap["exposed_alias"] is None
    assert snap["route_grant_id"] is None
