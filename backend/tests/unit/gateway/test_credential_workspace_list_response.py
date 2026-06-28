"""团队凭据 Tab 列表响应分级（metadata vs full）。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from domains.gateway.application.credential.management.credential_read_model import (
    CredentialReadModel,
)
from domains.gateway.presentation.schemas.credential_response import (
    METADATA_ONLY_API_KEY_MASKED,
    build_credential_response_for_team_workspace_list,
)


def _cred(
    *,
    created_by: uuid.UUID | None,
) -> CredentialReadModel:
    return CredentialReadModel(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        scope="team",
        scope_id=None,
        provider="openai",
        name="prod-key",
        api_base="https://api.example.com",
        api_bases=None,
        profile_id=None,
        profile_label=None,
        effective_api_base_openai=None,
        effective_api_base_anthropic=None,
        api_key_encrypted=b"enc",
        api_key_masked=None,
        extra={"k": "v"},
        is_active=True,
        visibility=None,
        created_by_user_id=created_by,
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("encryption_key", ["test-encryption-key-32bytes!!"])
def test_member_sees_metadata_only_for_others_credential(encryption_key: str) -> None:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    row = _cred(created_by=owner_id)

    resp = build_credential_response_for_team_workspace_list(
        row,
        encryption_key=encryption_key,
        actor_user_id=member_id,
        team_role="member",
        is_platform_admin=False,
    )

    assert resp.management_access == "metadata"
    assert resp.api_key_masked == METADATA_ONLY_API_KEY_MASKED
    assert resp.api_base == "https://api.example.com"
    assert resp.extra is None


@pytest.mark.parametrize("encryption_key", ["test-encryption-key-32bytes!!"])
def test_owner_gets_full_management_access(encryption_key: str) -> None:
    owner_id = uuid.uuid4()
    row = _cred(created_by=owner_id)

    resp = build_credential_response_for_team_workspace_list(
        row,
        encryption_key=encryption_key,
        actor_user_id=owner_id,
        team_role="member",
        is_platform_admin=False,
    )

    assert resp.management_access == "full"
    assert resp.api_key_masked != METADATA_ONLY_API_KEY_MASKED


@pytest.mark.parametrize("encryption_key", ["test-encryption-key-32bytes!!"])
def test_metadata_response_includes_api_base_not_secret(encryption_key: str) -> None:
    owner_id = uuid.uuid4()
    row = _cred(created_by=owner_id)

    from domains.gateway.presentation.schemas.credential_response import (
        build_credential_metadata_response,
    )

    resp = build_credential_metadata_response(row)

    assert resp.management_access == "metadata"
    assert resp.api_base == "https://api.example.com"
    assert resp.api_key_masked == METADATA_ONLY_API_KEY_MASKED
    assert resp.extra is None


def test_metadata_response_api_base_falls_back_to_provider_default() -> None:
    owner_id = uuid.uuid4()
    row = CredentialReadModel(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        scope="team",
        scope_id=None,
        provider="deepseek",
        name="team-key",
        api_base=None,
        api_bases=None,
        profile_id=None,
        profile_label=None,
        effective_api_base_openai="https://api.deepseek.com/v1",
        effective_api_base_anthropic=None,
        api_key_encrypted=b"enc",
        api_key_masked=None,
        extra=None,
        is_active=True,
        visibility=None,
        created_by_user_id=owner_id,
        created_at=datetime.now(UTC),
    )

    from domains.gateway.presentation.schemas.credential_response import (
        build_credential_metadata_response,
    )

    resp = build_credential_metadata_response(row)

    assert resp.management_access == "metadata"
    assert resp.api_base == "https://api.deepseek.com/v1"
    assert resp.api_key_masked == METADATA_ONLY_API_KEY_MASKED
