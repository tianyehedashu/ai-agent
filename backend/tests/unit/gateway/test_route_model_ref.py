"""route_model_ref 编解码单元测试。"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from domains.gateway.domain.route.route_model_ref import (
    encode_route_model_ref,
    parse_route_model_ref,
    resolve_parsed_ref_in_registry,
    resolve_route_ref_in_registry,
    route_ref_prefix_dispatchable,
)


def _id() -> UUID:
    return uuid4()


class _FakeRow:
    def __init__(self, name: str, tenant_id: UUID | None) -> None:
        self.name = name
        self.tenant_id = tenant_id


def test_encode_same_tenant_bare_name() -> None:
    owner = _id()
    assert (
        encode_route_model_ref(
            route_owner_tenant_id=owner,
            model_tenant_id=owner,
            model_name="gpt-4o",
            slug_by_tenant={owner: "my-personal"},
        )
        == "gpt-4o"
    )


def test_encode_cross_tenant_slug_prefix() -> None:
    owner = _id()
    shared = _id()
    assert (
        encode_route_model_ref(
            route_owner_tenant_id=owner,
            model_tenant_id=shared,
            model_name="gpt-4o",
            slug_by_tenant={owner: "my-personal", shared: "collab-team"},
        )
        == "collab-team/gpt-4o"
    )


def test_encode_system_bare_name() -> None:
    owner = _id()
    assert (
        encode_route_model_ref(
            route_owner_tenant_id=owner,
            model_tenant_id=None,
            model_name="sys-model",
            slug_by_tenant={owner: "my-personal"},
        )
        == "sys-model"
    )


def test_encode_rejects_ambiguous_slug() -> None:
    owner = _id()
    shared = _id()
    with pytest.raises(ValueError, match="ambiguous"):
        encode_route_model_ref(
            route_owner_tenant_id=owner,
            model_tenant_id=shared,
            model_name="gpt-4o",
            slug_by_tenant={owner: "my-personal", shared: "dup-slug"},
            ambiguous_slugs=frozenset({"dup-slug"}),
        )


def test_parse_bare_name_same_tenant() -> None:
    owner = _id()
    parsed = parse_route_model_ref(
        route_owner_tenant_id=owner,
        ref="gpt-4o",
        slug_to_tenant={"collab": _id()},
    )
    assert parsed.target_tenant_id == owner
    assert parsed.model_name == "gpt-4o"
    assert parsed.matched_slug is None


def test_parse_slug_prefix_cross_tenant() -> None:
    owner = _id()
    shared = _id()
    parsed = parse_route_model_ref(
        route_owner_tenant_id=owner,
        ref="collab-team/gpt-4o",
        slug_to_tenant={"collab-team": shared},
    )
    assert parsed.target_tenant_id == shared
    assert parsed.model_name == "gpt-4o"
    assert parsed.matched_slug == "collab-team"


def test_parse_vendor_slash_model_stays_local_when_slug_unknown() -> None:
    """vendor/model 形式但 slug 未命中 → 视为路由所属 tenant 裸名（与 vkey dispatch 非 strict 一致）。"""
    owner = _id()
    parsed = parse_route_model_ref(
        route_owner_tenant_id=owner,
        ref="openai/gpt-4o",
        slug_to_tenant={},
    )
    assert parsed.target_tenant_id == owner
    assert parsed.model_name == "openai/gpt-4o"
    assert parsed.matched_slug is None


def test_resolve_parsed_ref_in_registry() -> None:
    owner = _id()
    shared = _id()
    row = _FakeRow("gpt-4o", shared)
    by_team_name = {(str(shared), "gpt-4o"): row}
    parsed = parse_route_model_ref(
        route_owner_tenant_id=owner,
        ref="collab/gpt-4o",
        slug_to_tenant={"collab": shared},
    )
    assert resolve_parsed_ref_in_registry(parsed, by_team_name) is row


def test_resolve_system_fallback() -> None:
    owner = _id()
    sys_row = _FakeRow("sys-model", None)
    by_team_name = {(None, "sys-model"): sys_row}
    parsed = parse_route_model_ref(
        route_owner_tenant_id=owner,
        ref="sys-model",
        slug_to_tenant={},
    )
    assert parsed.target_tenant_id == owner
    assert resolve_parsed_ref_in_registry(parsed, by_team_name) is sys_row


def test_cross_team_missed_does_not_fallback_system() -> None:
    owner = _id()
    shared = _id()
    sys_row = _FakeRow("gpt-4o", None)
    by_team_name = {(None, "gpt-4o"): sys_row}
    parsed = parse_route_model_ref(
        route_owner_tenant_id=owner,
        ref="collab/gpt-4o",
        slug_to_tenant={"collab": shared},
    )
    assert parsed.matched_slug == "collab"
    assert resolve_parsed_ref_in_registry(parsed, by_team_name) is None


def test_shared_route_literal_slash_name_without_slug_prefix() -> None:
    owner = _id()
    row = _FakeRow("openai/gpt-4o", owner)
    by_team_name = {(str(owner), "openai/gpt-4o"): row}
    resolved = resolve_route_ref_in_registry(
        route_owner_tenant_id=owner,
        ref="openai/gpt-4o",
        by_team_name=by_team_name,
        slug_to_tenant={"openai": _id()},
        enable_slug_prefix=False,
    )
    assert resolved is row


def test_route_ref_prefix_dispatchable() -> None:
    owner = _id()
    shared = _id()
    assert route_ref_prefix_dispatchable(
        route_owner_tenant_id=owner,
        model_tenant_id=owner,
        slug="my-personal",
        ambiguous_slugs=frozenset(),
    )
    assert route_ref_prefix_dispatchable(
        route_owner_tenant_id=owner,
        model_tenant_id=shared,
        slug="collab",
        ambiguous_slugs=frozenset(),
    )
    assert not route_ref_prefix_dispatchable(
        route_owner_tenant_id=owner,
        model_tenant_id=shared,
        slug="dup",
        ambiguous_slugs=frozenset({"dup"}),
    )


def test_resolve_route_ref_in_registry_cross_team() -> None:
    owner = _id()
    shared = _id()
    row = _FakeRow("gpt-4o", shared)
    by_team_name = {(str(shared), "gpt-4o"): row}
    resolved = resolve_route_ref_in_registry(
        route_owner_tenant_id=owner,
        ref="collab/gpt-4o",
        by_team_name=by_team_name,
        slug_to_tenant={"collab": shared},
    )
    assert resolved is row
