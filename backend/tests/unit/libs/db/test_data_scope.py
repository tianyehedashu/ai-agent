"""DataScopeEnforcer 单元测试。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from libs.db.data_scope_clause import DataScopeEnforcer
from libs.iam.data_scope_policy import DataAction, DataResource, enforce_data_scope
from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


@pytest.fixture(autouse=True)
def _clear_ctx():
    clear_permission_context()
    yield
    clear_permission_context()


def test_visibility_clause_admin_no_filter() -> None:
    tid = uuid.uuid4()
    ctx = PermissionContext(user_id=uuid.uuid4(), role="admin", team_ids=frozenset({tid}))
    clause = DataScopeEnforcer.visibility_clause(GatewayModel, ctx)
    assert clause is None


def test_visibility_clause_restricts_to_team_ids() -> None:
    tid = uuid.uuid4()
    ctx = PermissionContext(user_id=uuid.uuid4(), role="user", team_ids=frozenset({tid}))
    set_permission_context(ctx)
    clause = DataScopeEnforcer.visibility_clause(GatewayModel, ctx)
    assert clause is not None


def test_enforce_data_scope() -> None:
    tid = uuid.uuid4()
    ctx = PermissionContext(user_id=uuid.uuid4(), role="user", team_ids=frozenset({tid}))
    assert enforce_data_scope(ctx, DataResource(kind="agent", tenant_id=tid), DataAction.READ)
    assert not enforce_data_scope(
        ctx, DataResource(kind="agent", tenant_id=uuid.uuid4()), DataAction.READ
    )
