"""租户显式鉴权辅助函数单元测试。"""

from __future__ import annotations

import uuid

import pytest

from domains.identity.presentation.deps import (
    ADMIN_ROLE,
    check_tenant_access,
    check_tenant_access_or_public,
)
from domains.identity.presentation.schemas import CurrentUser
from libs.exceptions import PermissionDeniedError
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


def _user(*, role: str = "user") -> CurrentUser:
    uid = uuid.uuid4()
    return CurrentUser(
        id=str(uid),
        email="test@example.com",
        name="Test User",
        is_anonymous=False,
        role=role,
    )


@pytest.mark.unit
class TestCheckTenantAccess:
    def test_allows_tenant_in_team_ids(self) -> None:
        tenant_id = uuid.uuid4()
        user = _user()
        set_permission_context(
            PermissionContext(user_id=uuid.UUID(user.id), team_ids=frozenset({tenant_id}))
        )
        try:
            check_tenant_access(tenant_id, user, "Agent")
        finally:
            clear_permission_context()

    def test_denies_foreign_tenant(self) -> None:
        user = _user()
        set_permission_context(
            PermissionContext(
                user_id=uuid.UUID(user.id),
                team_ids=frozenset({uuid.uuid4()}),
            )
        )
        try:
            with pytest.raises(PermissionDeniedError):
                check_tenant_access(uuid.uuid4(), user, "Agent")
        finally:
            clear_permission_context()

    def test_admin_bypasses_tenant_check(self) -> None:
        admin = _user(role=ADMIN_ROLE)
        check_tenant_access(uuid.uuid4(), admin, "Agent")

    def test_missing_context_denies(self) -> None:
        clear_permission_context()
        user = _user()
        with pytest.raises(PermissionDeniedError):
            check_tenant_access(uuid.uuid4(), user, "Agent")


@pytest.mark.unit
class TestCheckTenantAccessOrPublic:
    def test_public_resource_skips_tenant_check(self) -> None:
        clear_permission_context()
        user = _user()
        check_tenant_access_or_public(uuid.uuid4(), user, is_public=True, resource_name="Agent")

    def test_private_delegates_to_tenant_check(self) -> None:
        tenant_id = uuid.uuid4()
        user = _user()
        set_permission_context(
            PermissionContext(user_id=uuid.UUID(user.id), team_ids=frozenset({tenant_id}))
        )
        try:
            check_tenant_access_or_public(tenant_id, user, is_public=False, resource_name="Agent")
            with pytest.raises(PermissionDeniedError):
                check_tenant_access_or_public(
                    uuid.uuid4(), user, is_public=False, resource_name="Agent"
                )
        finally:
            clear_permission_context()
