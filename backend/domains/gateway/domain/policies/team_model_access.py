"""团队模型写侧权限：凭据绑定 create/update/delete 规则。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domains.gateway.domain.team_credential_access import (
    actor_owns_team_credential,
    can_manage_legacy_team_credential,
    is_legacy_shared_team_credential,
    is_team_admin_role,
)
from domains.tenancy.domain.errors import TeamPermissionDeniedError


class TeamModelCredentialView(Protocol):
    created_by_user_id: UUID | None


def can_create_model_on_team_credential(
    credential: TeamModelCredentialView,
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> bool:
    if actor_user_id is None:
        return False
    if actor_owns_team_credential(
        created_by_user_id=credential.created_by_user_id,
        actor_user_id=actor_user_id,
    ):
        return True
    return can_manage_legacy_team_credential(
        created_by_user_id=credential.created_by_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )


def can_update_team_model_on_credential(
    credential: TeamModelCredentialView,
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> bool:
    return can_create_model_on_team_credential(
        credential,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )


def can_delete_team_model_on_credential(
    credential: TeamModelCredentialView,
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> bool:
    if actor_user_id is None:
        return False
    if actor_owns_team_credential(
        created_by_user_id=credential.created_by_user_id,
        actor_user_id=actor_user_id,
    ):
        return True
    if is_legacy_shared_team_credential(credential.created_by_user_id):
        return can_manage_legacy_team_credential(
            created_by_user_id=credential.created_by_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
    if is_platform_admin:
        return False
    return is_team_admin_role(team_role)


def assert_can_create_model_on_team_credential(
    credential: TeamModelCredentialView,
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> None:
    if not can_create_model_on_team_credential(
        credential,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    ):
        raise TeamPermissionDeniedError("credential")


def assert_can_update_team_model_on_credential(
    credential: TeamModelCredentialView,
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> None:
    if not can_update_team_model_on_credential(
        credential,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    ):
        raise TeamPermissionDeniedError("model")


def assert_can_delete_team_model_on_credential(
    credential: TeamModelCredentialView,
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> None:
    if not can_delete_team_model_on_credential(
        credential,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    ):
        raise TeamPermissionDeniedError("model")


__all__ = [
    "TeamModelCredentialView",
    "assert_can_create_model_on_team_credential",
    "assert_can_delete_team_model_on_credential",
    "assert_can_update_team_model_on_credential",
    "can_create_model_on_team_credential",
    "can_delete_team_model_on_credential",
    "can_update_team_model_on_credential",
]
