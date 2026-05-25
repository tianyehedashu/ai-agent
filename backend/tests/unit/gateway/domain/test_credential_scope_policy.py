"""credential_scope 策略单测。"""

from __future__ import annotations

from domains.gateway.domain.policies.credential_scope import (
    is_system_credential_scope,
    registry_target_for_credential_scope,
    team_model_credential_scope_allowed,
)


def test_registry_target_for_credential_scope() -> None:
    assert registry_target_for_credential_scope("system") == "system"
    assert registry_target_for_credential_scope("team") == "team"
    assert registry_target_for_credential_scope("user") == "team"
    assert registry_target_for_credential_scope(None) == "team"


def test_team_model_credential_scope_allowed() -> None:
    assert team_model_credential_scope_allowed("team") is True
    assert team_model_credential_scope_allowed("system") is False
    assert is_system_credential_scope("system") is True
    assert is_system_credential_scope("team") is False
