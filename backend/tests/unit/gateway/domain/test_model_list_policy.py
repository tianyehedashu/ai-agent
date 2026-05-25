"""model_list_policy 单测。"""

from __future__ import annotations

from datetime import UTC, datetime

from domains.gateway.domain.policies.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
    availability_tier,
    is_model_unavailable,
    matches_connectivity_filter,
    matches_search,
    sort_registry_rows,
    summarize_connectivity,
)


class _Row:
    def __init__(
        self,
        *,
        name: str,
        enabled: bool = True,
        last_test_status: str | None = None,
        provider: str = "openai",
        real_model: str = "gpt-4",
    ) -> None:
        self.name = name
        self.enabled = enabled
        self.last_test_status = last_test_status
        self.provider = provider
        self.real_model = real_model
        self.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        self.last_tested_at = None


def test_is_model_unavailable() -> None:
    assert is_model_unavailable(enabled=False, last_test_status="success") is True
    assert is_model_unavailable(enabled=True, last_test_status="failed") is True
    assert is_model_unavailable(enabled=True, last_test_status="success", entitlement_status="exhausted")
    assert not is_model_unavailable(enabled=True, last_test_status="success")


def test_matches_search() -> None:
    assert matches_search(name="gpt-a", real_model="x", provider="openai", q="gpt")
    assert not matches_search(name="gpt-a", real_model="x", provider="openai", q="claude")


def test_sort_puts_unavailable_last() -> None:
    rows = [
        _Row(name="failed-one", last_test_status="failed"),
        _Row(name="alpha"),
        _Row(name="beta", enabled=False),
    ]
    sorted_rows = sort_registry_rows(rows, sort_field=ModelListSortField.NAME)
    assert [r.name for r in sorted_rows] == ["alpha", "beta", "failed-one"]


def test_sort_desc_keeps_unavailable_last() -> None:
    rows = [_Row(name="alpha"), _Row(name="zeta"), _Row(name="failed-one", last_test_status="failed")]
    sorted_rows = sort_registry_rows(
        rows,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.DESC,
    )
    assert [r.name for r in sorted_rows] == ["zeta", "alpha", "failed-one"]


def test_connectivity_filter() -> None:
    assert matches_connectivity_filter("failed", ModelListConnectivityFilter.FAILED)
    assert not matches_connectivity_filter("success", ModelListConnectivityFilter.FAILED)


def test_summarize_connectivity() -> None:
    rows = [
        _Row(name="a", last_test_status="success"),
        _Row(name="b", last_test_status="failed"),
        _Row(name="c"),
    ]
    summary = summarize_connectivity(rows)
    assert summary["total"] == 3
    assert summary["failed"] == 1
    assert summary["unknown"] == 1
    assert summary["unavailable"] == 1
    assert availability_tier(enabled=True, last_test_status="success") == 0


def test_sort_selector_items_puts_unavailable_last() -> None:
    from domains.gateway.domain.policies.model_list_policy import sort_selector_items

    items = [
        {"id": "failed", "display_name": "Failed", "last_test_status": "failed", "enabled": True},
        {"id": "ok", "display_name": "Alpha", "last_test_status": "success", "enabled": True},
        {"id": "off", "display_name": "Beta", "last_test_status": None, "enabled": False},
    ]
    sorted_items = sort_selector_items(items)
    assert [i["id"] for i in sorted_items] == ["ok", "off", "failed"]


def test_summarize_selector_items() -> None:
    from domains.gateway.domain.policies.model_list_policy import summarize_selector_items

    items = [
        {"last_test_status": "success", "enabled": True},
        {"last_test_status": "failed", "enabled": True},
        {"last_test_status": None, "enabled": True, "entitlement_status": "exhausted"},
    ]
    summary = summarize_selector_items(items)
    assert summary["total"] == 3
    assert summary["failed"] == 1
    assert summary["unavailable"] == 2
    assert summary["available"] == 1


def test_sort_selector_items_by_created_at_desc() -> None:
    from domains.gateway.domain.policies.model_list_policy import sort_selector_items

    items = [
        {
            "id": "old",
            "display_name": "Old",
            "created_at": "2026-01-01T00:00:00+00:00",
            "enabled": True,
            "last_test_status": "success",
        },
        {
            "id": "new",
            "display_name": "New",
            "created_at": "2026-06-01T00:00:00+00:00",
            "enabled": True,
            "last_test_status": "success",
        },
    ]
    sorted_items = sort_selector_items(
        items,
        sort_field=ModelListSortField.CREATED_AT,
        order=ModelListSortOrder.DESC,
    )
    assert [i["id"] for i in sorted_items] == ["new", "old"]


def test_parse_entitlement_list_status_invalid() -> None:
    from domains.gateway.domain.policies.model_list_policy import parse_entitlement_list_status

    assert parse_entitlement_list_status("exhausted") == "exhausted"
    assert parse_entitlement_list_status("bogus") == "none"
    assert parse_entitlement_list_status(None) == "none"
