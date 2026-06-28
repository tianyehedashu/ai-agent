"""Gateway 模型列表：可用性 tier、连通性筛选、排序（纯 domain）。"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol, TypeVar

from libs.exceptions import ValidationError

from .registry_model_types import REGISTRY_ABILITY_FILTER_VALUES

if TYPE_CHECKING:
    from collections.abc import Sequence

EntitlementListStatus = Literal["active", "exhausted", "resetting", "expired", "none"]

_ENTITLEMENT_STATUSES: frozenset[EntitlementListStatus] = frozenset(
    {"active", "exhausted", "resetting", "expired", "none"}
)


class ModelListSortField(StrEnum):
    NAME = "name"
    CREATED_AT = "created_at"
    PROVIDER = "provider"
    LAST_TESTED_AT = "last_tested_at"


class ModelListConnectivityFilter(StrEnum):
    ALL = "all"
    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ModelListSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class _RegistryRow(Protocol):
    enabled: bool
    name: str
    provider: str
    real_model: str
    created_at: datetime
    last_test_status: str | None
    last_tested_at: datetime | None


_RegistryRowT = TypeVar("_RegistryRowT", bound=_RegistryRow)


def parse_entitlement_list_status(value: object) -> EntitlementListStatus:
    if isinstance(value, str) and value in _ENTITLEMENT_STATUSES:
        return value
    return "none"


def is_registry_connectivity_available(
    *,
    enabled: bool,
    last_test_status: str | None,
) -> bool:
    """注册表行连通性 tier（不含 entitlement）；SQL ``_availability_order`` 须与此一致。"""
    return enabled and last_test_status != "failed"


def connectivity_health_key(last_test_status: str | None) -> ModelListConnectivityFilter:
    if last_test_status == "success":
        return ModelListConnectivityFilter.SUCCESS
    if last_test_status == "failed":
        return ModelListConnectivityFilter.FAILED
    return ModelListConnectivityFilter.UNKNOWN


def is_model_unavailable(
    *,
    enabled: bool,
    last_test_status: str | None,
    entitlement_status: EntitlementListStatus = "none",
) -> bool:
    if not enabled:
        return True
    if last_test_status == "failed":
        return True
    return entitlement_status in ("exhausted", "expired")


def availability_tier(
    *,
    enabled: bool,
    last_test_status: str | None,
    entitlement_status: EntitlementListStatus = "none",
) -> int:
    return (
        1
        if is_model_unavailable(
            enabled=enabled,
            last_test_status=last_test_status,
            entitlement_status=entitlement_status,
        )
        else 0
    )


def matches_connectivity_filter(
    last_test_status: str | None,
    filter_value: ModelListConnectivityFilter,
) -> bool:
    if filter_value == ModelListConnectivityFilter.ALL:
        return True
    return connectivity_health_key(last_test_status) == filter_value


def parse_registry_ability_filter(value: str | None) -> str | None:
    """解析列表 ``?type=`` / ``?capability=``（兼容）筛选值；非法则 ValidationError。"""
    if value is None:
        return None
    key = value.strip().lower()
    if not key:
        return None
    if key not in REGISTRY_ABILITY_FILTER_VALUES:
        raise ValidationError(
            f"无效的能力筛选: {value!r}；允许: {', '.join(sorted(REGISTRY_ABILITY_FILTER_VALUES))}"
        )
    return key


def matches_search(
    *,
    name: str,
    real_model: str,
    provider: str,
    q: str | None,
    credential_name: str | None = None,
) -> bool:
    if not q or not q.strip():
        return True
    needle = q.strip().lower()
    haystack = (name, real_model, provider)
    if any(needle in field.lower() for field in haystack):
        return True
    return bool(credential_name and needle in credential_name.lower())


def _sort_key_for_field(
    row: _RegistryRow,
    field: ModelListSortField,
) -> str | datetime:
    if field == ModelListSortField.CREATED_AT:
        return row.created_at
    if field == ModelListSortField.PROVIDER:
        return row.provider.lower()
    if field == ModelListSortField.LAST_TESTED_AT:
        return row.last_tested_at or datetime.min.replace(tzinfo=row.created_at.tzinfo)
    return row.name.lower()


def _parse_selector_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _selector_sort_key(
    item: dict[str, object],
    sort_field: ModelListSortField,
) -> str | datetime:
    if sort_field == ModelListSortField.PROVIDER:
        return str(item.get("provider") or "").lower()
    if sort_field == ModelListSortField.CREATED_AT:
        parsed = _parse_selector_datetime(item.get("created_at"))
        return parsed or datetime.min.replace(tzinfo=UTC)
    if sort_field == ModelListSortField.LAST_TESTED_AT:
        parsed = _parse_selector_datetime(item.get("last_tested_at"))
        return parsed or datetime.min.replace(tzinfo=UTC)
    display = str(item.get("display_name") or item.get("name") or item.get("id") or "")
    return display.lower()


def sort_registry_rows(
    rows: Sequence[_RegistryRowT],
    *,
    sort_field: ModelListSortField = ModelListSortField.NAME,
    order: ModelListSortOrder = ModelListSortOrder.ASC,
    entitlement_by_name: dict[str, EntitlementListStatus] | None = None,
) -> list[_RegistryRowT]:
    entitlements = entitlement_by_name or {}

    def sort_tuple(row: _RegistryRowT) -> tuple[int, str | datetime]:
        tier = availability_tier(
            enabled=row.enabled,
            last_test_status=row.last_test_status,
            entitlement_status=entitlements.get(row.name, "none"),
        )
        return tier, _sort_key_for_field(row, sort_field)

    sorted_rows = sorted(rows, key=sort_tuple)
    if order == ModelListSortOrder.DESC:
        # tier 仍保持升序（不可用置后）；仅对第二键反转
        available = [r for r in sorted_rows if sort_tuple(r)[0] == 0]
        unavailable = [r for r in sorted_rows if sort_tuple(r)[0] == 1]
        reverse_key = lambda row: _sort_key_for_field(row, sort_field)  # noqa: E731
        return sorted(available, key=reverse_key, reverse=True) + sorted(
            unavailable, key=reverse_key, reverse=True
        )
    return sorted_rows


def summarize_connectivity(
    rows: Sequence[_RegistryRowT],
    *,
    entitlement_by_name: dict[str, EntitlementListStatus] | None = None,
) -> dict[str, int]:
    entitlements = entitlement_by_name or {}
    success = failed = unknown = available = unavailable = 0
    for row in rows:
        key = connectivity_health_key(row.last_test_status)
        if key == ModelListConnectivityFilter.SUCCESS:
            success += 1
        elif key == ModelListConnectivityFilter.FAILED:
            failed += 1
        else:
            unknown += 1
        if is_model_unavailable(
            enabled=row.enabled,
            last_test_status=row.last_test_status,
            entitlement_status=entitlements.get(row.name, "none"),
        ):
            unavailable += 1
        else:
            available += 1
    total = len(rows)
    return {
        "total": total,
        "available": available,
        "unavailable": unavailable,
        "success": success,
        "failed": failed,
        "unknown": unknown,
    }


def summarize_selector_items(items: Sequence[dict[str, object]]) -> dict[str, int]:
    success = failed = unknown = 0
    available = unavailable = 0
    for item in items:
        last_test_status = item.get("last_test_status")
        status = (
            last_test_status
            if isinstance(last_test_status, str) or last_test_status is None
            else None
        )
        key = connectivity_health_key(status)
        if key == ModelListConnectivityFilter.SUCCESS:
            success += 1
        elif key == ModelListConnectivityFilter.FAILED:
            failed += 1
        else:
            unknown += 1
        entitlement = parse_entitlement_list_status(item.get("entitlement_status", "none"))
        if is_model_unavailable(
            enabled=bool(item.get("is_active", item.get("enabled", True))),
            last_test_status=status,
            entitlement_status=entitlement,
        ):
            unavailable += 1
        else:
            available += 1
    total = len(items)
    return {
        "total": total,
        "available": available,
        "unavailable": unavailable,
        "success": success,
        "failed": failed,
        "unknown": unknown,
    }


def sort_selector_items(
    items: Sequence[dict[str, object]],
    *,
    sort_field: ModelListSortField = ModelListSortField.NAME,
    order: ModelListSortOrder = ModelListSortOrder.ASC,
) -> list[dict[str, object]]:
    def tier(item: dict[str, object]) -> int:
        last_test_status = item.get("last_test_status")
        status = (
            last_test_status
            if isinstance(last_test_status, str) or last_test_status is None
            else None
        )
        entitlement = parse_entitlement_list_status(item.get("entitlement_status", "none"))
        return availability_tier(
            enabled=bool(item.get("is_active", item.get("enabled", True))),
            last_test_status=status,
            entitlement_status=entitlement,
        )

    sorted_items = sorted(
        items, key=lambda item: (tier(item), _selector_sort_key(item, sort_field))
    )
    if order == ModelListSortOrder.DESC:
        available = [i for i in sorted_items if tier(i) == 0]
        unavailable = [i for i in sorted_items if tier(i) == 1]
        reverse_key = lambda item: _selector_sort_key(item, sort_field)  # noqa: E731
        return sorted(available, key=reverse_key, reverse=True) + sorted(
            unavailable, key=reverse_key, reverse=True
        )
    return sorted_items


__all__ = [
    "EntitlementListStatus",
    "ModelListConnectivityFilter",
    "ModelListSortField",
    "ModelListSortOrder",
    "availability_tier",
    "connectivity_health_key",
    "is_model_unavailable",
    "is_registry_connectivity_available",
    "matches_connectivity_filter",
    "matches_search",
    "parse_entitlement_list_status",
    "parse_registry_ability_filter",
    "sort_registry_rows",
    "sort_selector_items",
    "summarize_connectivity",
    "summarize_selector_items",
]
