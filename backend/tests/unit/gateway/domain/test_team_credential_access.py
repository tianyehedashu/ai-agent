"""team_credential_access 纯函数测试。"""

from uuid import uuid4

import pytest

from domains.gateway.domain.errors import CredentialNotFoundError
from domains.gateway.domain.team_credential_access import (
    actor_owns_team_credential,
    assert_team_credential_readable_by_actor,
    assert_team_credential_writable_by_actor,
    can_filter_team_models_by_credential,
    can_read_team_credential,
    filter_team_credentials_visible_to_actor,
)
from domains.tenancy.domain.policies.team_role import TeamRole


class _FakeCred:
    def __init__(
        self,
        *,
        tenant_id,
        created_by_user_id,
    ) -> None:
        self.tenant_id = tenant_id
        self.created_by_user_id = created_by_user_id


def test_owner_only_reveal() -> None:
    owner = uuid4()
    other = uuid4()
    tenant = uuid4()
    cred = _FakeCred(tenant_id=tenant, created_by_user_id=owner)
    assert actor_owns_team_credential(
        created_by_user_id=owner,
        actor_user_id=owner,
    )
    assert can_read_team_credential(
        created_by_user_id=owner,
        actor_user_id=owner,
        team_role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )
    assert not can_read_team_credential(
        created_by_user_id=owner,
        actor_user_id=other,
        team_role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )
    assert not can_read_team_credential(
        created_by_user_id=owner,
        actor_user_id=other,
        team_role=TeamRole.ADMIN.value,
        is_platform_admin=True,
    )
    with pytest.raises(CredentialNotFoundError):
        assert_team_credential_readable_by_actor(
            cred,
            credential_id=uuid4(),
            tenant_id=tenant,
            actor_user_id=other,
            team_role=TeamRole.ADMIN.value,
            is_platform_admin=True,
        )
    assert_team_credential_writable_by_actor(
        cred,
        credential_id=uuid4(),
        tenant_id=tenant,
        actor_user_id=owner,
        team_role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )


def test_null_creator_not_readable() -> None:
    tenant = uuid4()
    actor = uuid4()
    null_cred = _FakeCred(tenant_id=tenant, created_by_user_id=None)
    assert not can_read_team_credential(
        created_by_user_id=None,
        actor_user_id=actor,
        team_role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )
    visible = filter_team_credentials_visible_to_actor(
        [null_cred],
        actor_user_id=actor,
        team_role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )
    assert visible == []


def test_filter_visible_credentials() -> None:
    owner = uuid4()
    tenant = uuid4()
    own = _FakeCred(tenant_id=tenant, created_by_user_id=owner)
    other = _FakeCred(tenant_id=tenant, created_by_user_id=uuid4())
    visible = filter_team_credentials_visible_to_actor(
        [own, other],
        actor_user_id=owner,
        team_role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )
    assert visible == [own]


def test_can_filter_team_models_by_credential() -> None:
    owner = uuid4()
    member = uuid4()
    peer = uuid4()
    admin = uuid4()

    assert can_filter_team_models_by_credential(
        created_by_user_id=member,
        actor_user_id=member,
        creator_team_role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )
    assert can_filter_team_models_by_credential(
        created_by_user_id=owner,
        actor_user_id=member,
        creator_team_role=TeamRole.OWNER.value,
        is_platform_admin=False,
    )
    assert not can_filter_team_models_by_credential(
        created_by_user_id=member,
        actor_user_id=owner,
        creator_team_role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )
    assert not can_filter_team_models_by_credential(
        created_by_user_id=member,
        actor_user_id=peer,
        creator_team_role=TeamRole.MEMBER.value,
        is_platform_admin=False,
    )
    assert not can_filter_team_models_by_credential(
        created_by_user_id=None,
        actor_user_id=member,
        creator_team_role=None,
        is_platform_admin=False,
    )
    assert can_filter_team_models_by_credential(
        created_by_user_id=admin,
        actor_user_id=member,
        creator_team_role=TeamRole.ADMIN.value,
        is_platform_admin=False,
    )
