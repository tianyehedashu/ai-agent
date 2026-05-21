"""``enforce_data_scope`` 与 ``check_tenant_access`` 行为一致。"""

from __future__ import annotations

import uuid

import pytest

from domains.identity.presentation.deps import ADMIN_ROLE, check_tenant_access
from domains.identity.presentation.schemas import CurrentUser
from libs.iam.data_scope_policy import DataAction, DataResource, enforce_data_scope
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)
from libs.exceptions import PermissionDeniedError

pytestmark = pytest.mark.unit


def _registered_user(role: str = "user") -> CurrentUser:
    uid = uuid.uuid4()
    return CurrentUser(
        id=str(uid),
        email="u@example.com",
        name="User",
        is_anonymous=False,
        role=role,
    )


def _enforce_matches_check(
    ctx: PermissionContext,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    *,
    expect_allowed: bool,
) -> None:
    resource = DataResource(kind="Resource", tenant_id=tenant_id)
    enforce_ok = enforce_data_scope(ctx, resource, DataAction.READ)
    assert enforce_ok is expect_allowed

    set_permission_context(ctx)
    try:
        if expect_allowed:
            check_tenant_access(tenant_id, user, "Resource")
        else:
            with pytest.raises(PermissionDeniedError):
                check_tenant_access(tenant_id, user, "Resource")
    finally:
        clear_permission_context()


class TestDataScopeEquivalence:
    def test_admin_always_allowed(self) -> None:
        user = _registered_user(role=ADMIN_ROLE)
        tenant_id = uuid.uuid4()
        ctx = PermissionContext(user_id=uuid.uuid4(), role=ADMIN_ROLE, team_ids=frozenset())
        _enforce_matches_check(ctx, tenant_id, user, expect_allowed=True)

    def test_empty_team_ids_denied(self) -> None:
        user = _registered_user()
        tenant_id = uuid.uuid4()
        ctx = PermissionContext(user_id=uuid.uuid4(), role="user", team_ids=frozenset())
        _enforce_matches_check(ctx, tenant_id, user, expect_allowed=False)

    def test_tenant_in_team_ids_allowed(self) -> None:
        user = _registered_user()
        tenant_id = uuid.uuid4()
        ctx = PermissionContext(
            user_id=uuid.uuid4(),
            role="user",
            team_ids=frozenset({tenant_id}),
        )
        _enforce_matches_check(ctx, tenant_id, user, expect_allowed=True)

    def test_tenant_not_in_team_ids_denied(self) -> None:
        user = _registered_user()
        tenant_id = uuid.uuid4()
        other = uuid.uuid4()
        ctx = PermissionContext(
            user_id=uuid.uuid4(),
            role="user",
            team_ids=frozenset({other}),
        )
        _enforce_matches_check(ctx, tenant_id, user, expect_allowed=False)

    def test_no_permission_context_denied(self) -> None:
        user = _registered_user()
        tenant_id = uuid.uuid4()
        clear_permission_context()
        with pytest.raises(PermissionDeniedError):
            check_tenant_access(tenant_id, user, "Resource")
