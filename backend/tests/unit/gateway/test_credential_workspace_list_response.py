"""团队凭据 Tab 列表响应分级（metadata vs full）。"""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest

from domains.gateway.application.management.credential_read_model import CredentialReadModel
from domains.gateway.presentation.credential_response import (
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
    assert resp.api_base is None
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
