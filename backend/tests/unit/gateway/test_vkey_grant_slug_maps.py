"""grant team slug 映射纯函数单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.application.vkey_team_resolution import (
    build_slug_by_tenant_id,
    build_unique_slug_to_tenant_id,
)


def test_build_slug_by_tenant_id_preserves_all_tenants() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    rows = [(a, "team-a"), (b, "team-b")]
    assert build_slug_by_tenant_id(rows) == {a: "team-a", b: "team-b"}


def test_build_unique_slug_to_tenant_id_excludes_homonym_slugs() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    unique_id = uuid.uuid4()
    rows = [(a, "same-slug"), (b, "same-slug"), (unique_id, "unique-slug")]
    mapping = build_unique_slug_to_tenant_id(rows)
    assert "same-slug" not in mapping
    assert mapping["unique-slug"] == unique_id
