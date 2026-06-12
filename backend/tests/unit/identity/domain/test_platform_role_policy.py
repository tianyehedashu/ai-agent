"""platform_role_policy 单元测试。"""

from __future__ import annotations

import uuid

import pytest

from domains.identity.domain.policies.platform_role_policy import (
    assert_bootstrap_grant_admin,
    assert_bootstrap_revoke_admin,
    assert_emergency_grant_admin,
    assert_can_change_platform_role,
    is_assignable_platform_role,
)
from domains.identity.domain.rbac import Role
from libs.exceptions import PermissionDeniedError, ValidationError


@pytest.mark.unit
class TestIsAssignablePlatformRole:
    @pytest.mark.parametrize(
        "role",
        [Role.ADMIN.value, Role.USER.value, Role.VIEWER.value],
    )
    def test_assignable(self, role: str) -> None:
        assert is_assignable_platform_role(role) is True

    @pytest.mark.parametrize("role", ["anonymous", "superuser", ""])
    def test_not_assignable(self, role: str) -> None:
        assert is_assignable_platform_role(role) is False


@pytest.mark.unit
class TestAssertCanChangePlatformRole:
    def _ids(self) -> tuple[uuid.UUID, uuid.UUID]:
        return uuid.uuid4(), uuid.uuid4()

    def test_admin_can_promote_user(self) -> None:
        actor_id, target_id = self._ids()
        assert_can_change_platform_role(
            actor_role=Role.ADMIN.value,
            actor_id=actor_id,
            target_id=target_id,
            target_current_role=Role.USER.value,
            new_role=Role.ADMIN.value,
        )

    def test_non_admin_denied(self) -> None:
        actor_id, target_id = self._ids()
        with pytest.raises(PermissionDeniedError):
            assert_can_change_platform_role(
                actor_role=Role.USER.value,
                actor_id=actor_id,
                target_id=target_id,
                target_current_role=Role.USER.value,
                new_role=Role.ADMIN.value,
            )

    def test_anonymous_target_denied(self) -> None:
        actor_id, target_id = self._ids()
        with pytest.raises(ValidationError, match="anonymous"):
            assert_can_change_platform_role(
                actor_role=Role.ADMIN.value,
                actor_id=actor_id,
                target_id=target_id,
                target_current_role="anonymous",
                new_role=Role.USER.value,
            )

    def test_self_change_denied(self) -> None:
        user_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="own"):
            assert_can_change_platform_role(
                actor_role=Role.ADMIN.value,
                actor_id=user_id,
                target_id=user_id,
                target_current_role=Role.ADMIN.value,
                new_role=Role.USER.value,
            )

    def test_last_admin_demotion_denied(self) -> None:
        actor_id, target_id = self._ids()
        with pytest.raises(ValidationError, match="last platform administrator"):
            assert_can_change_platform_role(
                actor_role=Role.ADMIN.value,
                actor_id=actor_id,
                target_id=target_id,
                target_current_role=Role.ADMIN.value,
                new_role=Role.USER.value,
                admin_count=1,
            )

    def test_admin_demotion_allowed_when_multiple_admins(self) -> None:
        actor_id, target_id = self._ids()
        assert_can_change_platform_role(
            actor_role=Role.ADMIN.value,
            actor_id=actor_id,
            target_id=target_id,
            target_current_role=Role.ADMIN.value,
            new_role=Role.USER.value,
            admin_count=2,
        )

    def test_invalid_new_role(self) -> None:
        actor_id, target_id = self._ids()
        with pytest.raises(ValidationError, match="Invalid platform role"):
            assert_can_change_platform_role(
                actor_role=Role.ADMIN.value,
                actor_id=actor_id,
                target_id=target_id,
                target_current_role=Role.USER.value,
                new_role="bogus",
            )


@pytest.mark.unit
class TestBootstrapPlatformRolePolicy:
    def test_grant_when_no_admin(self) -> None:
        assert_bootstrap_grant_admin(
            target_current_role=Role.USER.value,
            admin_count=0,
        )

    def test_grant_rejected_when_admin_exists(self) -> None:
        with pytest.raises(ValidationError, match="already exists"):
            assert_bootstrap_grant_admin(
                target_current_role=Role.USER.value,
                admin_count=1,
            )

    def test_revoke_when_two_admins(self) -> None:
        assert_bootstrap_revoke_admin(
            target_current_role=Role.ADMIN.value,
            admin_count=2,
        )

    def test_revoke_rejected_for_last_admin(self) -> None:
        with pytest.raises(ValidationError, match="last platform administrator"):
            assert_bootstrap_revoke_admin(
                target_current_role=Role.ADMIN.value,
                admin_count=1,
            )

    def test_emergency_grant_when_admin_exists(self) -> None:
        assert_emergency_grant_admin(target_current_role=Role.USER.value)

    def test_emergency_grant_rejects_already_admin(self) -> None:
        with pytest.raises(ValidationError, match="already"):
            assert_emergency_grant_admin(target_current_role=Role.ADMIN.value)
