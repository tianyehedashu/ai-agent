"""凭据跨 scope 复制策略（源 = reveal 级，目标 = membership）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from domains.gateway.domain.errors import CredentialNotFoundError, TeamPermissionDeniedError
from domains.gateway.domain.policies.credential_scope import (
    assert_user_credential_importable,
    is_system_credential_scope,
)
from domains.gateway.domain.team_credential_access import assert_team_credential_readable_by_actor
from libs.exceptions import ValidationError

if TYPE_CHECKING:
    import uuid

CredentialCopyKind = Literal["personal", "team"]


@dataclass(frozen=True)
class CredentialCopyScope:
    kind: CredentialCopyKind
    team_id: uuid.UUID | None = None


def assert_copy_endpoints_valid(
    *,
    source: CredentialCopyScope,
    destination: CredentialCopyScope,
) -> None:
    """校验复制端点组合合法（不含 membership）。"""
    if source.kind == "team" and source.team_id is None:
        raise ValidationError("source.team_id is required when source.kind is team")
    if destination.kind == "team" and destination.team_id is None:
        raise ValidationError("destination.team_id is required when destination.kind is team")
    if source.kind == "personal" and destination.kind == "personal":
        raise ValidationError("Cannot copy credentials from personal to personal")
    if (
        source.kind == "team"
        and destination.kind == "team"
        and source.team_id == destination.team_id
    ):
        raise ValidationError("Source and destination team must differ")


def assert_credential_copy_destination_allowed(
    *,
    destination: CredentialCopyScope,
    destination_team_role: str | None,
    is_platform_admin: bool,
) -> None:
    """目标 scope 合法且 actor 具备 member+ 写入上下文。"""
    if destination.kind == "personal":
        return
    if destination.team_id is None or destination_team_role is None:
        raise TeamPermissionDeniedError(str(destination.team_id or ""))
    if is_platform_admin:
        return
    from domains.tenancy.domain.policies.team_role import TeamRole

    if destination_team_role not in (
        TeamRole.OWNER.value,
        TeamRole.ADMIN.value,
        TeamRole.MEMBER.value,
    ):
        raise TeamPermissionDeniedError(str(destination.team_id))


def assert_credential_copy_source_allowed(
    credential: object,
    *,
    source: CredentialCopyScope,
    actor_user_id: uuid.UUID,
    is_platform_admin: bool,
    source_team_role: str | None,
    permission_denied_tenant_id: uuid.UUID,
) -> None:
    """单条凭据是否可作复制源；失败抛 CredentialNotFoundError（防枚举）。"""
    cred_id = getattr(credential, "id", "")
    scope = getattr(credential, "scope", None)
    tenant_id = getattr(credential, "tenant_id", None)

    if is_system_credential_scope(scope):
        raise CredentialNotFoundError(str(cred_id))

    if source.kind == "personal":
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

    if source.team_id is None or source_team_role is None:
        raise CredentialNotFoundError(str(cred_id))
    if tenant_id != source.team_id:
        raise CredentialNotFoundError(str(cred_id))
    assert_team_credential_readable_by_actor(
        credential,
        credential_id=cred_id,
        tenant_id=source.team_id,
        actor_user_id=actor_user_id,
        team_role=source_team_role,
        is_platform_admin=is_platform_admin,
    )


def credential_copy_failure_reason(exc: BaseException) -> str:
    """批量复制失败项对外 reason（避免泄露内部异常细节）。"""
    if isinstance(exc, CredentialNotFoundError):
        return "credential not found"
    if isinstance(exc, ValidationError):
        return str(exc)
    return "copy failed"


__all__ = [
    "CredentialCopyKind",
    "CredentialCopyScope",
    "assert_copy_endpoints_valid",
    "assert_credential_copy_destination_allowed",
    "assert_credential_copy_source_allowed",
    "credential_copy_failure_reason",
]
