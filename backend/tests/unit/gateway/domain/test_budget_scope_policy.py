"""budget_scope_policy 策略单元测试。"""

from __future__ import annotations

from dataclasses import dataclass
import uuid

import pytest

from domains.gateway.domain.policies.budget_scope_policy import (
    BudgetListFilters,
    BudgetTeamContext,
    budget_target_allowed,
    filter_budget_rows,
    normalize_budget_list_filters,
    plan_admin_budget_fetch,
)
from domains.gateway.domain.types import BudgetScope


@dataclass
class _BudgetRow:
    target_kind: str
    model_name: str | None


@pytest.mark.unit
def test_normalize_budget_list_filters_strips_model_name() -> None:
    filters = normalize_budget_list_filters("user", "  gpt-4  ")
    assert filters.target_kind == "user"
    assert filters.model_name == "gpt-4"

    empty = normalize_budget_list_filters(None, "   ")
    assert empty.model_name is None


@pytest.mark.unit
def test_plan_admin_budget_fetch_all_scopes() -> None:
    plan = plan_admin_budget_fetch(target_kind=None, include_system=True)
    assert plan.fetch_tenant is True
    assert plan.fetch_user is True
    assert plan.fetch_key is True
    assert plan.fetch_system is True


@pytest.mark.unit
def test_plan_admin_budget_fetch_single_scope() -> None:
    plan = plan_admin_budget_fetch(target_kind=BudgetScope.KEY.value, include_system=True)
    assert plan.fetch_tenant is False
    assert plan.fetch_user is False
    assert plan.fetch_key is True
    assert plan.fetch_system is False


@pytest.mark.unit
def test_plan_admin_budget_fetch_system_requires_include_system() -> None:
    plan = plan_admin_budget_fetch(target_kind=BudgetScope.SYSTEM.value, include_system=False)
    assert plan.fetch_system is False


@pytest.mark.unit
def test_filter_budget_rows_by_kind_and_model() -> None:
    rows = [
        _BudgetRow(BudgetScope.USER.value, "gpt-4"),
        _BudgetRow(BudgetScope.USER.value, "claude-3"),
        _BudgetRow(BudgetScope.TENANT.value, "gpt-4"),
    ]
    filters = BudgetListFilters(target_kind=BudgetScope.USER.value, model_name="gpt-4")
    assert filter_budget_rows(rows, filters) == [_BudgetRow(BudgetScope.USER.value, "gpt-4")]


@pytest.mark.unit
def test_budget_target_allowed_tenant() -> None:
    tenant_id = uuid.uuid4()
    ctx = BudgetTeamContext(
        tenant_id=tenant_id,
        member_user_ids=frozenset(),
        is_platform_admin=False,
    )
    assert budget_target_allowed(BudgetScope.TENANT.value, tenant_id, ctx) is True
    assert budget_target_allowed(BudgetScope.TENANT.value, uuid.uuid4(), ctx) is False


@pytest.mark.unit
def test_budget_target_allowed_user_membership() -> None:
    tenant_id = uuid.uuid4()
    member_id = uuid.uuid4()
    outsider_id = uuid.uuid4()
    ctx = BudgetTeamContext(
        tenant_id=tenant_id,
        member_user_ids=frozenset({member_id}),
        is_platform_admin=False,
    )
    assert budget_target_allowed(BudgetScope.USER.value, member_id, ctx) is True
    assert budget_target_allowed(BudgetScope.USER.value, outsider_id, ctx) is False
    assert budget_target_allowed(BudgetScope.USER.value, None, ctx) is False


@pytest.mark.unit
def test_budget_target_allowed_key_requires_flag() -> None:
    tenant_id = uuid.uuid4()
    key_id = uuid.uuid4()
    ctx = BudgetTeamContext(
        tenant_id=tenant_id,
        member_user_ids=frozenset(),
        is_platform_admin=False,
    )
    assert budget_target_allowed(BudgetScope.KEY.value, key_id, ctx, key_belongs_to_team=True) is True
    assert budget_target_allowed(BudgetScope.KEY.value, key_id, ctx, key_belongs_to_team=False) is False
    assert budget_target_allowed(BudgetScope.KEY.value, key_id, ctx) is False


@pytest.mark.unit
def test_budget_target_allowed_system_platform_admin() -> None:
    tenant_id = uuid.uuid4()
    member_ctx = BudgetTeamContext(
        tenant_id=tenant_id,
        member_user_ids=frozenset(),
        is_platform_admin=False,
    )
    admin_ctx = BudgetTeamContext(
        tenant_id=tenant_id,
        member_user_ids=frozenset(),
        is_platform_admin=True,
    )
    assert budget_target_allowed(BudgetScope.SYSTEM.value, None, member_ctx) is False
    assert budget_target_allowed(BudgetScope.SYSTEM.value, None, admin_ctx) is True
