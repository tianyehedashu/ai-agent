"""vkey_grant_slug_policy 域纯规则单测。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.vkey.vkey_grant_slug_policy import (
    build_slug_by_tenant_id,
    build_unique_slug_to_tenant_id,
    find_ambiguous_grant_slugs,
    grant_tenant_prefix_dispatchable,
)


def test_build_unique_slug_to_tenant_id_excludes_homonym_slugs() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    unique_id = uuid.uuid4()
    rows = [(a, "same-slug"), (b, "same-slug"), (unique_id, "unique-slug")]
    mapping = build_unique_slug_to_tenant_id(rows)
    assert "same-slug" not in mapping
    assert mapping["unique-slug"] == unique_id


def test_find_ambiguous_grant_slugs() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rows = [(a, "dup"), (b, "dup"), (c, "unique")]
    assert find_ambiguous_grant_slugs(rows) == frozenset({"dup"})


def test_grant_tenant_prefix_dispatchable_homonym_grant_skipped() -> None:
    bound, grant = uuid.uuid4(), uuid.uuid4()
    ambiguous = frozenset({"same-slug"})
    assert grant_tenant_prefix_dispatchable(
        tenant_id=bound,
        bound_team_id=bound,
        slug="same-slug",
        ambiguous_slugs=ambiguous,
    )
    assert not grant_tenant_prefix_dispatchable(
        tenant_id=grant,
        bound_team_id=bound,
        slug="same-slug",
        ambiguous_slugs=ambiguous,
    )


def test_build_slug_by_tenant_id_preserves_all_tenants() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    rows = [(a, "team-a"), (b, "team-b")]
    assert build_slug_by_tenant_id(rows) == {a: "team-a", b: "team-b"}
