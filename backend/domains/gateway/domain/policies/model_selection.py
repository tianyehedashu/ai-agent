"""Gateway 模型/路由：system 与 tenant 行合并规则（纯函数）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, TypeVar

RegistryKind = Literal["team", "system"]


class _NamedModel(Protocol):
    name: str
    enabled: bool


class _VirtualModelRoute(Protocol):
    virtual_model: str
    enabled: bool


_T = TypeVar("_T", bound=_NamedModel)
_R = TypeVar("_R", bound=_VirtualModelRoute)


def registry_kind_for_merged_row(record: object) -> RegistryKind:
    """合并列表中的注册行：``gateway_models`` 有 ``tenant_id``，``system_gateway_models`` 无。"""
    if getattr(record, "tenant_id", None) is not None:
        return "team"
    return "system"


def merge_named_rows_tenant_overrides_system(
    tenant_rows: Sequence[_T],
    system_rows: Sequence[_T],
    *,
    only_enabled: bool = True,
) -> list[_T]:
    """同名时保留 tenant 行，system 行仅补 tenant 未覆盖的名称。"""
    by_name: dict[str, _T] = {}
    for row in tenant_rows:
        if only_enabled and not row.enabled:
            continue
        by_name[row.name] = row
    for row in system_rows:
        if only_enabled and not row.enabled:
            continue
        by_name.setdefault(row.name, row)
    return sorted(by_name.values(), key=lambda r: r.name)


def merge_virtual_model_rows_tenant_overrides_system(
    tenant_rows: Sequence[_R],
    system_rows: Sequence[_R],
    *,
    only_enabled: bool = True,
) -> list[_R]:
    """``virtual_model`` 同名时保留 tenant 行，system 行仅补 tenant 未覆盖的名称。"""
    by_name: dict[str, _R] = {}
    for row in tenant_rows:
        if only_enabled and not row.enabled:
            continue
        by_name[row.virtual_model] = row
    for row in system_rows:
        if only_enabled and not row.enabled:
            continue
        by_name.setdefault(row.virtual_model, row)
    return sorted(by_name.values(), key=lambda r: r.virtual_model)


__all__ = [
    "RegistryKind",
    "merge_named_rows_tenant_overrides_system",
    "merge_virtual_model_rows_tenant_overrides_system",
    "registry_kind_for_merged_row",
]
