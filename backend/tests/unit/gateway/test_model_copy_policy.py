"""model_copy_policy 单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
import uuid

import pytest

from domains.gateway.domain.catalog.model_copy_policy import (
    assert_model_copy_credential_plan_valid,
    assert_model_copy_destination_credential_allowed,
    assert_model_copy_destination_differs,
    assert_model_copy_source_credential_allowed,
    model_copy_failure_reason,
)
from domains.gateway.domain.errors import CredentialNotFoundError
from domains.tenancy.domain.errors import TeamPermissionDeniedError
from libs.exceptions import ValidationError


@dataclass
class _Cred:
    id: uuid.UUID
    scope: str | None
    tenant_id: uuid.UUID | None
    provider: str
    created_by_user_id: uuid.UUID | None = None
    scope_id: uuid.UUID | None = None


def test_destination_must_differ() -> None:
    tid = uuid.uuid4()
    with pytest.raises(ValidationError, match="must differ"):
        assert_model_copy_destination_differs(
            source_tenant_id=tid,
            destination_team_id=tid,
        )


def test_credential_plan_existing_requires_dest_id() -> None:
    with pytest.raises(ValidationError, match="destination_credential_id"):
        assert_model_copy_credential_plan_valid(
            mode="existing",
            destination_credential_id=None,
        )


def test_credential_plan_copy_forbids_dest_id() -> None:
    with pytest.raises(ValidationError, match="must be omitted"):
        assert_model_copy_credential_plan_valid(
            mode="copy_credential",
            destination_credential_id=uuid.uuid4(),
        )


def test_team_source_denied_for_non_owner() -> None:
    actor = uuid.uuid4()
    owner = uuid.uuid4()
    tenant = uuid.uuid4()
    cred = _Cred(
        id=uuid.uuid4(),
        scope="team",
        tenant_id=tenant,
        provider="openai",
        created_by_user_id=owner,
    )
    with pytest.raises(CredentialNotFoundError):
        assert_model_copy_source_credential_allowed(
            cred,
            source_tenant_id=tenant,
            personal_team_id=uuid.uuid4(),
            actor_user_id=actor,
            is_platform_admin=False,
            source_team_role="member",
            permission_denied_tenant_id=uuid.uuid4(),
        )


def test_team_source_allowed_for_owner() -> None:
    actor = uuid.uuid4()
    tenant = uuid.uuid4()
    cred = _Cred(
        id=uuid.uuid4(),
        scope="team",
        tenant_id=tenant,
        provider="openai",
        created_by_user_id=actor,
    )
    assert_model_copy_source_credential_allowed(
        cred,
        source_tenant_id=tenant,
        personal_team_id=uuid.uuid4(),
        actor_user_id=actor,
        is_platform_admin=False,
        source_team_role="member",
        permission_denied_tenant_id=uuid.uuid4(),
    )


def test_destination_provider_mismatch() -> None:
    actor = uuid.uuid4()
    tenant = uuid.uuid4()
    cred = _Cred(
        id=uuid.uuid4(),
        scope="team",
        tenant_id=tenant,
        provider="anthropic",
        created_by_user_id=actor,
    )
    with pytest.raises(ValidationError, match="provider mismatch"):
        assert_model_copy_destination_credential_allowed(
            cred,
            destination_team_id=tenant,
            source_provider="openai",
            actor_user_id=actor,
            destination_team_role="owner",
            is_platform_admin=False,
        )


def test_model_copy_failure_reason_maps_permission() -> None:
    assert model_copy_failure_reason(CredentialNotFoundError("x")) == "credential not found"
    assert model_copy_failure_reason(TeamPermissionDeniedError("x")) != "credential not found"


def test_copy_request_rejects_duplicate_source_credential_plans() -> None:
    from pydantic import ValidationError as PydanticValidationError

    from domains.gateway.presentation.schemas.model_copy import CopyModelsToTeamRequest

    cred_id = uuid.uuid4()
    with pytest.raises(PydanticValidationError):
        CopyModelsToTeamRequest(
            model_ids=[uuid.uuid4()],
            destination_team_id=uuid.uuid4(),
            credential_plans=[
                {
                    "source_credential_id": cred_id,
                    "mode": "copy_credential",
                },
                {
                    "source_credential_id": cred_id,
                    "mode": "copy_credential",
                },
            ],
        )
