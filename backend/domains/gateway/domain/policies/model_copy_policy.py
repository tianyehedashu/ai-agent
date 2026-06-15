"""模型跨团队子集复制策略（源 = reveal，目标 = create）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from domains.gateway.domain.errors import CredentialNotFoundError, ManagementEntityNotFoundError
from domains.gateway.domain.policies.credential_scope import (
    assert_user_credential_importable,
    is_system_credential_scope,
)
from domains.gateway.domain.policies.team_model_access import (
    assert_can_create_model_on_team_credential,
)
from domains.gateway.domain.team_credential_access import assert_team_credential_readable_by_actor
from domains.tenancy.domain.errors import TeamPermissionDeniedError
from libs.exceptions import ValidationError

if TYPE_CHECKING:
    import uuid

ModelCopyCredentialMode = Literal["existing", "copy_credential"]


def assert_model_copy_destination_differs(
    *,
    source_tenant_id: uuid.UUID,
    destination_team_id: uuid.UUID,
) -> None:
    if source_tenant_id == destination_team_id:
        raise ValidationError("Source and destination team must differ")


def assert_model_copy_source_credential_allowed(
    credential: object,
    *,
    source_tenant_id: uuid.UUID,
    personal_team_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    is_platform_admin: bool,
    source_team_role: str | None,
    permission_denied_tenant_id: uuid.UUID,
) -> None:
    """源凭据 reveal 级；失败抛 CredentialNotFoundError（防枚举）。"""
    cred_id = getattr(credential, "id", "")
    scope = getattr(credential, "scope", None)
    tenant_id = getattr(credential, "tenant_id", None)

    if is_system_credential_scope(scope):
        raise CredentialNotFoundError(str(cred_id))

    if source_tenant_id == personal_team_id:
        if scope != "user":
            raise CredentialNotFoundError(str(cred_id))
        try:
            assert_user_credential_importable(
                credential,
                actor_user_id=actor_user_id,
                is_platform_admin=is_platform_admin,
                tenant_id=permission_denied_tenant_id,
            )
        except TeamPermissionDeniedError:
            raise CredentialNotFoundError(str(cred_id)) from None
        return

    if source_team_role is None:
        raise CredentialNotFoundError(str(cred_id))
    if tenant_id != source_tenant_id:
        raise CredentialNotFoundError(str(cred_id))
    assert_team_credential_readable_by_actor(
        credential,
        credential_id=cred_id,
        tenant_id=source_tenant_id,
        actor_user_id=actor_user_id,
        team_role=source_team_role,
        is_platform_admin=is_platform_admin,
    )


def assert_model_copy_destination_credential_allowed(
    credential: object,
    *,
    destination_team_id: uuid.UUID,
    source_provider: str,
    actor_user_id: uuid.UUID,
    destination_team_role: str,
    is_platform_admin: bool,
) -> None:
    """目标凭据须同 provider 且 actor 可 create 模型。"""
    cred_id = getattr(credential, "id", "")
    tenant_id = getattr(credential, "tenant_id", None)
    provider = str(getattr(credential, "provider", "")).strip().lower()
    scope = getattr(credential, "scope", None)

    if is_system_credential_scope(scope):
        raise CredentialNotFoundError(str(cred_id))
    if tenant_id != destination_team_id:
        raise CredentialNotFoundError(str(cred_id))
    if provider != source_provider.strip().lower():
        raise ValidationError("destination credential provider mismatch")
    assert_can_create_model_on_team_credential(
        credential,
        actor_user_id=actor_user_id,
        team_role=destination_team_role,
        is_platform_admin=is_platform_admin,
    )


def assert_model_copy_credential_plan_valid(
    *,
    mode: ModelCopyCredentialMode,
    destination_credential_id: uuid.UUID | None,
) -> None:
    if mode == "existing" and destination_credential_id is None:
        raise ValidationError("destination_credential_id is required when mode is existing")
    if mode == "copy_credential" and destination_credential_id is not None:
        raise ValidationError("destination_credential_id must be omitted when mode is copy_credential")


def model_copy_failure_reason(exc: BaseException) -> str:
    if isinstance(exc, (CredentialNotFoundError, ManagementEntityNotFoundError)):
        return "model not found" if isinstance(exc, ManagementEntityNotFoundError) else "credential not found"
    if isinstance(exc, ValidationError):
        return str(exc)
    return "copy failed"


__all__ = [
    "ModelCopyCredentialMode",
    "assert_model_copy_credential_plan_valid",
    "assert_model_copy_destination_credential_allowed",
    "assert_model_copy_destination_differs",
    "assert_model_copy_source_credential_allowed",
    "model_copy_failure_reason",
]
