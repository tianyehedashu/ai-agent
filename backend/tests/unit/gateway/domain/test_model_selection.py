"""model_selection 合并策略。"""

from __future__ import annotations

from dataclasses import dataclass

from domains.gateway.domain.policies.model_selection import (
    merge_named_rows_tenant_overrides_system,
    registry_kind_for_merged_row,
)


@dataclass
class _Row:
    name: str
    enabled: bool = True


@dataclass
class _TeamRow:
    name: str
    tenant_id: object


def test_registry_kind_team_when_tenant_id_present() -> None:
    assert registry_kind_for_merged_row(_TeamRow("m", tenant_id=object())) == "team"


def test_registry_kind_system_without_tenant_id() -> None:
    assert registry_kind_for_merged_row(_Row("m")) == "system"


def test_merge_tenant_overrides_system_name() -> None:
    tenant = [_Row("a"), _Row("b")]
    system = [_Row("a"), _Row("c")]
    merged = merge_named_rows_tenant_overrides_system(tenant, system)
    names = {r.name for r in merged}
    assert names == {"a", "b", "c"}
    by_name = {r.name: r for r in merged}
    assert by_name["a"] in tenant


def test_merge_respects_only_enabled_false_for_disabled_tenant_rows() -> None:
    tenant = [_Row("enabled"), _Row("disabled", enabled=False)]
    system = [_Row("sys-only")]
    merged = merge_named_rows_tenant_overrides_system(
        tenant, system, only_enabled=False
    )
    assert {r.name for r in merged} == {"enabled", "disabled", "sys-only"}


def test_merge_skips_disabled_rows_when_only_enabled_true() -> None:
    tenant = [_Row("enabled"), _Row("disabled", enabled=False)]
    merged = merge_named_rows_tenant_overrides_system(tenant, [], only_enabled=True)
    assert {r.name for r in merged} == {"enabled"}


@dataclass
class _RouteRow:
    virtual_model: str
    enabled: bool = True


def test_merge_virtual_model_tenant_overrides_system() -> None:
    from domains.gateway.domain.policies.model_selection import (
        merge_virtual_model_rows_tenant_overrides_system,
    )

    tenant = [_RouteRow("fast"), _RouteRow("team-only")]
    system = [_RouteRow("fast"), _RouteRow("global")]
    merged = merge_virtual_model_rows_tenant_overrides_system(tenant, system)
    names = {r.virtual_model for r in merged}
    assert names == {"fast", "team-only", "global"}
    by_name = {r.virtual_model: r for r in merged}
    assert by_name["fast"] in tenant
