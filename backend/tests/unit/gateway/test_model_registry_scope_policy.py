"""model_registry_scope 策略单测。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.catalog.model_registry_scope import (
    RegistryScope,
    exclude_user_scope_credentials_for_registry,
    filter_system_registry_rows,
    is_requestable_registry_scope,
    uses_merged_registry_list,
)
from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row


class _TeamRow:
    tenant_id = object()
    last_test_status = None


class _SystemRow:
    last_test_status = None


@pytest.mark.parametrize(
    ("registry_scope", "expected"),
    [
        ("team", True),
        ("system", False),
        ("callable", False),
        ("requestable", False),
        ("system_requestable", False),
    ],
)
def test_exclude_user_scope_credentials_for_registry(
    registry_scope: RegistryScope,
    expected: bool,
) -> None:
    assert exclude_user_scope_credentials_for_registry(registry_scope) is expected


@pytest.mark.parametrize(
    ("registry_scope", "expected"),
    [
        ("requestable", True),
        ("system_requestable", True),
        ("callable", False),
        ("team", False),
        ("system", False),
    ],
)
def test_is_requestable_registry_scope(registry_scope: RegistryScope, expected: bool) -> None:
    assert is_requestable_registry_scope(registry_scope) is expected


@pytest.mark.parametrize(
    ("registry_scope", "expected"),
    [
        ("callable", True),
        ("requestable", True),
        ("system_requestable", True),
        ("team", False),
        ("system", False),
    ],
)
def test_uses_merged_registry_list(registry_scope: RegistryScope, expected: bool) -> None:
    assert uses_merged_registry_list(registry_scope) is expected


def test_filter_system_registry_rows() -> None:
    rows = [_TeamRow(), _SystemRow(), _SystemRow()]
    filtered = filter_system_registry_rows(rows)
    assert len(filtered) == 2
    assert all(registry_kind_for_merged_row(row) == "system" for row in filtered)
