"""team_credential_management_access 单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.team_credential_access import team_credential_management_access


def test_member_sees_metadata_for_others_team_credential() -> None:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    assert (
        team_credential_management_access(
            scope="team",
            tenant_id=uuid.uuid4(),
            created_by_user_id=owner_id,
            actor_user_id=member_id,
            team_role="member",
            is_platform_admin=False,
        )
        == "metadata"
    )


def test_owner_gets_full_access() -> None:
    owner_id = uuid.uuid4()
    assert (
        team_credential_management_access(
            scope="team",
            tenant_id=uuid.uuid4(),
            created_by_user_id=owner_id,
            actor_user_id=owner_id,
            team_role="member",
            is_platform_admin=False,
        )
        == "full"
    )


def test_legacy_admin_gets_full() -> None:
    admin_id = uuid.uuid4()
    assert (
        team_credential_management_access(
            scope="team",
            tenant_id=uuid.uuid4(),
            created_by_user_id=None,
            actor_user_id=admin_id,
            team_role="admin",
            is_platform_admin=False,
        )
        == "full"
    )


def test_system_credential_metadata_for_non_platform_admin() -> None:
    assert (
        team_credential_management_access(
            scope="system",
            tenant_id=None,
            created_by_user_id=None,
            actor_user_id=uuid.uuid4(),
            team_role="member",
            is_platform_admin=False,
        )
        == "metadata"
    )
