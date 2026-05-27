"""团队 scope 凭据管理面访问控制（与 virtual_key_access 对齐：创建者私有）。"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domains.gateway.domain.errors import CredentialNotFoundError
from domains.tenancy.domain.policies.team_role import TeamRole


class TeamCredentialAccessView(Protocol):
    """断言访问权限所需的最小凭据视图。"""

    tenant_id: UUID | None
    created_by_user_id: UUID | None


def is_legacy_shared_team_credential(created_by_user_id: UUID | None) -> bool:
    """NULL 创建者表示迁移前 legacy 共享凭据（team admin+ 可管）。"""
    return created_by_user_id is None


def actor_owns_team_credential(
    *,
    created_by_user_id: UUID | None,
    actor_user_id: UUID,
) -> bool:
    return (
        created_by_user_id is not None
        and created_by_user_id == actor_user_id
    )


def is_team_admin_role(team_role: str) -> bool:
    return team_role in (TeamRole.OWNER.value, TeamRole.ADMIN.value)


def can_manage_legacy_team_credential(
    *,
    created_by_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> bool:
    if not is_legacy_shared_team_credential(created_by_user_id):
        return False
    return is_team_admin_role(team_role)


def can_read_team_credential(
    *,
    created_by_user_id: UUID | None,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> bool:
    if actor_user_id is None:
        return False
    if actor_owns_team_credential(
        created_by_user_id=created_by_user_id,
        actor_user_id=actor_user_id,
    ):
        return True
    return can_manage_legacy_team_credential(
        created_by_user_id=created_by_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )


def can_write_team_credential(
    *,
    created_by_user_id: UUID | None,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> bool:
    return can_read_team_credential(
        created_by_user_id=created_by_user_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )


def assert_team_credential_readable_by_actor(
    record: TeamCredentialAccessView | None,
    *,
    credential_id: UUID,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> TeamCredentialAccessView:
    """校验 actor 是否可读团队凭据；失败抛 CredentialNotFoundError（防枚举）。"""
    if (
        record is None
        or record.tenant_id is None
        or record.tenant_id != tenant_id
    ):
        raise CredentialNotFoundError(str(credential_id))
    if not can_read_team_credential(
        created_by_user_id=record.created_by_user_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    ):
        raise CredentialNotFoundError(str(credential_id))
    return record


def assert_team_credential_writable_by_actor(
    record: TeamCredentialAccessView | None,
    *,
    credential_id: UUID,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> TeamCredentialAccessView:
    if (
        record is None
        or record.tenant_id is None
        or record.tenant_id != tenant_id
    ):
        raise CredentialNotFoundError(str(credential_id))
    if not can_write_team_credential(
        created_by_user_id=record.created_by_user_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    ):
        raise CredentialNotFoundError(str(credential_id))
    return record


def filter_team_credentials_visible_to_actor(
    credentials: list[TeamCredentialAccessView],
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> list[TeamCredentialAccessView]:
    if actor_user_id is None:
        return []
    return [
        cred
        for cred in credentials
        if can_read_team_credential(
            created_by_user_id=cred.created_by_user_id,
            actor_user_id=actor_user_id,
            team_role=team_role,
            is_platform_admin=is_platform_admin,
        )
    ]


__all__ = [
    "TeamCredentialAccessView",
    "actor_owns_team_credential",
    "assert_team_credential_readable_by_actor",
    "assert_team_credential_writable_by_actor",
    "can_manage_legacy_team_credential",
    "can_read_team_credential",
    "can_write_team_credential",
    "filter_team_credentials_visible_to_actor",
    "is_legacy_shared_team_credential",
    "is_team_admin_role",
]
