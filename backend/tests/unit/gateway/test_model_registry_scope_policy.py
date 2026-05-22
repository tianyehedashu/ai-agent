"""model_registry_scope 策略单测。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.policies.model_registry_scope import (
    RegistryScope,
    exclude_user_scope_credentials_for_registry,
)


@pytest.mark.parametrize(
    ("registry_scope", "expected"),
    [
        ("team", True),
        ("system", False),
        ("callable", False),
        ("requestable", False),
    ],
)
def test_exclude_user_scope_credentials_for_registry(
    registry_scope: RegistryScope,
    expected: bool,
) -> None:
    assert exclude_user_scope_credentials_for_registry(registry_scope) is expected
