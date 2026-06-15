"""团队 scope 凭据管理面访问控制（与 virtual_key_access 对齐：创建者私有）。"""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from domains.gateway.domain.errors import CredentialNotFoundError
from domains.tenancy.domain.policies.team_role import TeamRole, is_admin_or_owner_team_role

CredentialManagementAccess = Literal["full", "metadata"]


class TeamCredentialAccessView(Protocol):
    """断言访问权限所需的最小凭据视图。"""

    tenant_id: UUID | None
    created_by_user_id: UUID | None


def actor_owns_team_credential(
    *,
    created_by_user_id: UUID | None,
    actor_user_id: UUID,
) -> bool:
    return created_by_user_id is not None and created_by_user_id == actor_user_id


def is_team_admin_role(team_role: str) -> bool:
    return is_admin_or_owner_team_role(team_role)


def can_filter_team_models_by_credential(
    *,
    created_by_user_id: UUID | None,
    actor_user_id: UUID,
    creator_team_role: str | None,
    is_platform_admin: bool,
) -> bool:
    """模型列表 ``credential_id`` 筛选：弱于 reveal，成员可按 owner/admin 凭据筛模型。"""
    if is_platform_admin:
        return True
    if actor_owns_team_credential(
        created_by_user_id=created_by_user_id,
        actor_user_id=actor_user_id,
    ):
        return True
    return is_team_admin_role(creator_team_role or TeamRole.MEMBER.value)


def can_read_team_credential(
    *,
    created_by_user_id: UUID | None,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> bool:
    if actor_user_id is None:
        return False
    return actor_owns_team_credential(
        created_by_user_id=created_by_user_id,
        actor_user_id=actor_user_id,
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


def _assert_team_credential_accessible(
    record: TeamCredentialAccessView | None,
    *,
    credential_id: UUID,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
    can_access_fn,
) -> TeamCredentialAccessView:
    """可复用的凭据访问断言体（readable/writable 共用）。"""
    if record is None or record.tenant_id is None or record.tenant_id != tenant_id:
        raise CredentialNotFoundError(str(credential_id))
    if not can_access_fn(
        created_by_user_id=record.created_by_user_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    ):
        raise CredentialNotFoundError(str(credential_id))
    return record


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
    return _assert_team_credential_accessible(
        record,
        credential_id=credential_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
        can_access_fn=can_read_team_credential,
    )


def assert_team_credential_writable_by_actor(
    record: TeamCredentialAccessView | None,
    *,
    credential_id: UUID,
    tenant_id: UUID,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> TeamCredentialAccessView:
    """当前 can_write 与 can_read 等价，直接委托可读断言。

    若未来读写权限分离，请改用独立的 can_write 调用。
    """
    return _assert_team_credential_accessible(
        record,
        credential_id=credential_id,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
        can_access_fn=can_write_team_credential,
    )


def team_credential_management_access(
    *,
    scope: str | None,
    tenant_id: UUID | None,
    created_by_user_id: UUID | None,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
) -> CredentialManagementAccess:
    """团队凭据 Tab 列表：成员可见全部行，敏感字段按是否具备 reveal 权限分级。"""
    api_scope = "team" if scope == "team" or tenant_id is not None else scope
    if api_scope == "system":
        return "full" if is_platform_admin else "metadata"
    if api_scope != "team":
        return "full" if actor_user_id is not None else "metadata"
    if can_read_team_credential(
        created_by_user_id=created_by_user_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    ):
        return "full"
    return "metadata"


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
    "CredentialManagementAccess",
    "TeamCredentialAccessView",
    "actor_owns_team_credential",
    "assert_team_credential_readable_by_actor",
    "assert_team_credential_writable_by_actor",
    "can_filter_team_models_by_credential",
    "can_read_team_credential",
    "can_write_team_credential",
    "filter_team_credentials_visible_to_actor",
    "is_team_admin_role",
    "team_credential_management_access",
]
