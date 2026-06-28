"""凭据提供者展示标签。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from domains.gateway.application.credential.management.credential_creator_labels import (
    collect_creator_user_ids,
    credential_creator_display_label,
    credential_creator_labels_for_read_models,
)
from domains.gateway.application.credential.management.credential_read_model import CredentialReadModel
from domains.identity.application.ports import UserSummaryView


def _team_cred(*, created_by: UUID | None = None) -> CredentialReadModel:
    return CredentialReadModel(
        id=uuid4(),
        tenant_id=uuid4(),
        scope="team",
        scope_id=None,
        provider="volcengine",
        name="huoshan-common",
        api_base=None,
        extra=None,
        is_active=True,
        created_at=datetime.now(UTC),
        api_key_encrypted="enc",
        created_by_user_id=created_by,
    )


def test_collect_creator_user_ids_includes_team_and_byok() -> None:
    owner_id = uuid4()
    user_id = uuid4()
    team_cred = _team_cred(created_by=owner_id)
    byok = CredentialReadModel(
        id=uuid4(),
        tenant_id=None,
        scope="user",
        scope_id=user_id,
        provider="openai",
        name="my-key",
        api_base=None,
        extra=None,
        is_active=True,
        created_at=datetime.now(UTC),
        api_key_encrypted="enc",
        created_by_user_id=None,
    )
    ids = collect_creator_user_ids([team_cred, byok])
    assert owner_id in ids
    assert user_id in ids


def test_credential_creator_display_label_system_and_team() -> None:
    system = CredentialReadModel(
        id=uuid4(),
        tenant_id=None,
        scope="system",
        scope_id=None,
        provider="volcengine",
        name="app-config-default",
        api_base=None,
        extra={"managed_by": "config"},
        is_active=True,
        created_at=datetime.now(UTC),
        api_key_encrypted="enc",
    )
    assert credential_creator_display_label(system, user_label=None) == "平台（配置同步）"

    team = _team_cred()
    assert credential_creator_display_label(team, user_label="dlt@example.com") == "dlt@example.com"


def test_credential_creator_labels_for_read_models() -> None:
    owner_id = uuid4()
    cred = _team_cred(created_by=owner_id)
    summaries = {owner_id: UserSummaryView(name="Leo", email="leo@example.com")}
    labels = credential_creator_labels_for_read_models([cred], summaries)
    assert labels[cred.id] == "Leo"
