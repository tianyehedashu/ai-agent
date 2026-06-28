"""credential_copy_policy 单元测试。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.credential.credential_copy_policy import (
    CredentialCopyScope,
    assert_copy_endpoints_valid,
    assert_credential_copy_destination_allowed,
    assert_credential_copy_source_allowed,
    credential_copy_failure_reason,
)
from domains.gateway.domain.errors import CredentialNotFoundError, TeamPermissionDeniedError
from libs.exceptions import ValidationError


def test_assert_copy_endpoints_rejects_personal_to_personal() -> None:
    with pytest.raises(ValidationError):
        assert_copy_endpoints_valid(
            source=CredentialCopyScope(kind="personal"),
            destination=CredentialCopyScope(kind="personal"),
        )


def test_assert_copy_endpoints_rejects_same_team() -> None:
    team_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        assert_copy_endpoints_valid(
            source=CredentialCopyScope(kind="team", team_id=team_id),
            destination=CredentialCopyScope(kind="team", team_id=team_id),
        )


def test_assert_copy_destination_requires_team_role() -> None:
    team_id = uuid.uuid4()
    with pytest.raises(TeamPermissionDeniedError):
        assert_credential_copy_destination_allowed(
            destination=CredentialCopyScope(kind="team", team_id=team_id),
            destination_team_role=None,
            is_platform_admin=False,
        )


def test_assert_copy_destination_rejects_unknown_team_role() -> None:
    team_id = uuid.uuid4()
    with pytest.raises(TeamPermissionDeniedError):
        assert_credential_copy_destination_allowed(
            destination=CredentialCopyScope(kind="team", team_id=team_id),
            destination_team_role="guest",
            is_platform_admin=False,
        )


def test_assert_copy_destination_allows_platform_admin_without_membership() -> None:
    team_id = uuid.uuid4()
    assert_credential_copy_destination_allowed(
        destination=CredentialCopyScope(kind="team", team_id=team_id),
        destination_team_role="admin",
        is_platform_admin=True,
    )


def test_assert_copy_source_team_mismatch_tenant() -> None:
    actor_id = uuid.uuid4()
    source_team = uuid.uuid4()

    class _Cred:
        id = uuid.uuid4()
        scope = None
        tenant_id = uuid.uuid4()
        scope_id = None
        created_by_user_id = actor_id

    with pytest.raises(CredentialNotFoundError):
        assert_credential_copy_source_allowed(
            _Cred(),
            source=CredentialCopyScope(kind="team", team_id=source_team),
            actor_user_id=actor_id,
            is_platform_admin=False,
            source_team_role="owner",
            permission_denied_tenant_id=source_team,
        )


def test_assert_copy_source_personal_non_owner_maps_to_not_found() -> None:
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    team_id = uuid.uuid4()

    class _Cred:
        id = uuid.uuid4()
        scope = "user"
        tenant_id = None
        scope_id = owner_id

    with pytest.raises(CredentialNotFoundError):
        assert_credential_copy_source_allowed(
            _Cred(),
            source=CredentialCopyScope(kind="personal"),
            actor_user_id=other_id,
            is_platform_admin=False,
            source_team_role=None,
            permission_denied_tenant_id=team_id,
        )


def test_credential_copy_failure_reason_masks_internal_errors() -> None:
    assert credential_copy_failure_reason(CredentialNotFoundError("x")) == "credential not found"
    assert credential_copy_failure_reason(RuntimeError("db exploded")) == "copy failed"
    assert credential_copy_failure_reason(TeamPermissionDeniedError("team")) == "copy failed"
