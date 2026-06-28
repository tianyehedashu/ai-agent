"""模型注册表 ``registry_scope`` 读侧过滤策略（纯函数）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeVar

from .model_selection import registry_kind_for_merged_row

if TYPE_CHECKING:
    from collections.abc import Sequence

RegistryScope = Literal["team", "system", "callable", "requestable", "system_requestable"]

_T = TypeVar("_T")


def exclude_user_scope_credentials_for_registry(registry_scope: RegistryScope) -> bool:
    """``registry_scope=team`` 时排除 ``scope=user``（BYOK）凭据绑定的租户注册行。

    personal team 工作区与共享团队共用 ``tenant_id`` 轴；BYOK 物理上落在 personal
    tenant 但不应出现在「团队注册表」Tab。``callable`` / ``requestable`` / ``/v1/models``
    仍须包含 BYOK 别名。
    """
    return registry_scope == "team"


def is_requestable_registry_scope(registry_scope: RegistryScope) -> bool:
    """``requestable`` / ``system_requestable``：仅 enabled 且连通性未 failed。"""
    return registry_scope in ("requestable", "system_requestable")


def uses_merged_registry_list(registry_scope: RegistryScope) -> bool:
    """经租户可见性合并后的列表（非纯 tenant/system 注册表 SQL 路径）。"""
    return registry_scope in ("callable", "requestable", "system_requestable")


def filter_system_registry_rows(rows: Sequence[_T]) -> list[_T]:
    """合并列表中仅保留 ``registry_kind=system`` 的平台注册行。"""
    return [row for row in rows if registry_kind_for_merged_row(row) == "system"]


__all__ = [
    "RegistryScope",
    "exclude_user_scope_credentials_for_registry",
    "filter_system_registry_rows",
    "is_requestable_registry_scope",
    "uses_merged_registry_list",
]
