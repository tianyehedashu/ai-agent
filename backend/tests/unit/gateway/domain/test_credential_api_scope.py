"""credential_api_scope 纯函数单测。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.types import (
    CredentialScope,
    credential_api_scope,
    normalize_downstream_pricing_scope,
)


def test_tenant_row_scope_null_maps_to_team() -> None:
    tid = uuid.uuid4()
    assert credential_api_scope(scope=None, tenant_id=tid) == CredentialScope.TEAM.value


def test_user_byok_scope() -> None:
    assert credential_api_scope(scope="user", tenant_id=None) == CredentialScope.USER.value


def test_system_unscoped_defaults_to_system() -> None:
    assert credential_api_scope(scope=None, tenant_id=None) == CredentialScope.SYSTEM.value


def test_explicit_system() -> None:
    assert credential_api_scope(scope="system", tenant_id=None) == CredentialScope.SYSTEM.value


def test_normalize_downstream_pricing_scope_team_to_tenant() -> None:
    assert normalize_downstream_pricing_scope("team") == "tenant"
    assert normalize_downstream_pricing_scope("global") == "global"
