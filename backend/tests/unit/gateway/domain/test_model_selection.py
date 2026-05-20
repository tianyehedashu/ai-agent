"""model_selection 合并策略。"""

from __future__ import annotations

from dataclasses import dataclass

from domains.gateway.domain.policies.model_selection import merge_named_rows_tenant_overrides_system


@dataclass
class _Row:
    name: str
    enabled: bool = True


def test_merge_tenant_overrides_system_name() -> None:
    tenant = [_Row("a"), _Row("b")]
    system = [_Row("a"), _Row("c")]
    merged = merge_named_rows_tenant_overrides_system(tenant, system)
    names = {r.name for r in merged}
    assert names == {"a", "b", "c"}
    by_name = {r.name: r for r in merged}
    assert by_name["a"] in tenant
