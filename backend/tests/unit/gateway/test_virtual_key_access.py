"""domain/virtual_key_access 纯函数单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.domain.errors import (
    SystemVirtualKeyForbiddenError,
    VirtualKeyNotFoundError,
)
from domains.gateway.domain.virtual_key_access import (
    assert_virtual_key_accessible_by_actor,
    filter_virtual_keys_visible_to_actor,
)


class _FakeVKey:
    def __init__(
        self,
        *,
        team_id: uuid.UUID,
        created_by: uuid.UUID | None,
        is_system: bool = False,
        is_active: bool = True,
    ) -> None:
        self.tenant_id = team_id
        self.created_by_user_id = created_by
        self.is_system = is_system
        self.is_active = is_active


@pytest.mark.unit
def test_assert_rejects_missing_or_wrong_team() -> None:
    team_id = uuid.uuid4()
    other_team = uuid.uuid4()
    key_id = str(uuid.uuid4())
    record = _FakeVKey(team_id=other_team, created_by=uuid.uuid4())

    with pytest.raises(VirtualKeyNotFoundError):
        assert_virtual_key_accessible_by_actor(
            None,
            key_id=key_id,
            tenant_id=team_id,
            actor_user_id=uuid.uuid4(),
            team_role="owner",
            is_platform_admin=False,
        )
    with pytest.raises(VirtualKeyNotFoundError):
        assert_virtual_key_accessible_by_actor(
            record,
            key_id=key_id,
            tenant_id=team_id,
            actor_user_id=uuid.uuid4(),
            team_role="owner",
            is_platform_admin=False,
        )


@pytest.mark.unit
def test_assert_rejects_inactive_when_required() -> None:
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    key_id = str(uuid.uuid4())
    record = _FakeVKey(team_id=team_id, created_by=user_id, is_active=False)

    with pytest.raises(VirtualKeyNotFoundError):
        assert_virtual_key_accessible_by_actor(
            record,
            key_id=key_id,
            tenant_id=team_id,
            actor_user_id=user_id,
            team_role="owner",
            is_platform_admin=False,
            require_active=True,
        )

    assert (
        assert_virtual_key_accessible_by_actor(
            record,
            key_id=key_id,
            tenant_id=team_id,
            actor_user_id=user_id,
            team_role="owner",
            is_platform_admin=False,
            require_active=False,
        )
        is record
    )


@pytest.mark.unit
def test_assert_rejects_system_and_non_creator() -> None:
    team_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    key_id = str(uuid.uuid4())
    system = _FakeVKey(team_id=team_id, created_by=None, is_system=True)
    member_key = _FakeVKey(team_id=team_id, created_by=member_id)

    with pytest.raises(SystemVirtualKeyForbiddenError):
        assert_virtual_key_accessible_by_actor(
            system,
            key_id=key_id,
            tenant_id=team_id,
            actor_user_id=owner_id,
            team_role="owner",
            is_platform_admin=False,
        )

    with pytest.raises(VirtualKeyNotFoundError):
        assert_virtual_key_accessible_by_actor(
            member_key,
            key_id=key_id,
            tenant_id=team_id,
            actor_user_id=owner_id,
            team_role="owner",
            is_platform_admin=False,
        )


@pytest.mark.unit
def test_filter_only_creator_keys() -> None:
    team_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    own = _FakeVKey(team_id=team_id, created_by=member_id)
    other = _FakeVKey(team_id=team_id, created_by=owner_id)
    keys = [own, other]

    assert filter_virtual_keys_visible_to_actor(
        keys,
        actor_user_id=member_id,
        team_role="member",
        is_platform_admin=False,
    ) == [own]

    assert filter_virtual_keys_visible_to_actor(
        keys,
        actor_user_id=owner_id,
        team_role="owner",
        is_platform_admin=False,
    ) == [other]
