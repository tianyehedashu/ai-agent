"""platform_user_admin_policy 单元测试。"""

from __future__ import annotations

import uuid

import pytest

from domains.identity.domain.policies.platform_user_admin_policy import (
    assert_can_admin_manage_user,
    assert_can_set_user_active,
)
from domains.identity.domain.rbac import Role
from libs.exceptions import PermissionDeniedError, ValidationError


def test_assert_can_admin_manage_user_requires_admin() -> None:
    with pytest.raises(PermissionDeniedError):
        assert_can_admin_manage_user(actor_role=Role.USER.value, target_current_role=Role.USER.value)


def test_assert_can_admin_manage_user_rejects_anonymous() -> None:
    with pytest.raises(ValidationError, match="anonymous"):
        assert_can_admin_manage_user(actor_role=Role.ADMIN.value, target_current_role="anonymous")


def test_assert_can_set_user_active_rejects_self_deactivate() -> None:
    user_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="own account"):
        assert_can_set_user_active(actor_id=user_id, target_id=user_id, new_active=False)
