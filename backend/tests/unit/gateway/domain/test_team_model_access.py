"""team_model_access 纯函数测试。"""

from uuid import uuid4

import pytest

from domains.gateway.domain.catalog.team_model_access import (
    actor_created_model,
    assert_can_create_model_on_team_credential,
    assert_can_delete_team_model_on_credential,
    assert_can_update_team_model_on_credential,
    can_delete_team_model_on_credential,
)
from domains.tenancy.domain.errors import TeamPermissionDeniedError
from domains.tenancy.domain.policies.team_role import TeamRole


class _FakeCred:
    def __init__(self, created_by_user_id) -> None:
        self.created_by_user_id = created_by_user_id


def test_member_can_create_on_own_credential() -> None:
    owner = uuid4()
    cred = _FakeCred(created_by_user_id=owner)
    assert_can_create_model_on_team_credential(
        cred,
        actor_user_id=owner,
        team_role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )


def test_admin_cannot_create_on_member_credential() -> None:
    owner = uuid4()
    admin = uuid4()
    cred = _FakeCred(created_by_user_id=owner)
    with pytest.raises(TeamPermissionDeniedError):
        assert_can_create_model_on_team_credential(
            cred,
            actor_user_id=admin,
            team_role=TeamRole.ADMIN.value,
            is_platform_admin=False,
        )


def test_admin_can_delete_member_model() -> None:
    owner = uuid4()
    admin = uuid4()
    cred = _FakeCred(created_by_user_id=owner)
    assert can_delete_team_model_on_credential(
        cred,
        actor_user_id=admin,
        team_role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )
    assert_can_delete_team_model_on_credential(
        cred,
        actor_user_id=admin,
        team_role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )


def test_admin_can_update_member_model() -> None:
    owner = uuid4()
    admin = uuid4()
    cred = _FakeCred(created_by_user_id=owner)
    assert_can_update_team_model_on_credential(
        cred,
        actor_user_id=admin,
        team_role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )


def test_actor_created_model() -> None:
    user = uuid4()
    other = uuid4()
    assert actor_created_model(model_created_by_user_id=user, actor_user_id=user) is True
    assert actor_created_model(model_created_by_user_id=user, actor_user_id=other) is False
    assert actor_created_model(model_created_by_user_id=None, actor_user_id=user) is False
