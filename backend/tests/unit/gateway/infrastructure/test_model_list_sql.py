"""model_list_sql 聚合 SQL 回归：connectivity_summary 不得与子查询笛卡尔积。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.policies.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
)
from domains.gateway.infrastructure.repositories.model_list_sql import (
    _summary_select,
    build_system_list_stmt,
    build_tenant_list_stmt,
)


def test_summary_select_aggregates_subquery_columns_not_base_table() -> None:
    """修复前：外层 aggregate 引用 ORM 表列会导致 CROSS JOIN，total 变为 N×N。"""
    base = build_system_list_stmt(
        only_enabled=False,
        capability=None,
        provider=None,
        credential_id=None,
        enabled=None,
        q=None,
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
    )
    subq = base.order_by(None).subquery()
    summary_stmt = _summary_select(
        enabled_col=subq.c.enabled,
        status_col=subq.c.last_test_status,
    ).select_from(subq)

    compiled = str(summary_stmt.compile()).lower()
    # 外层 aggregate 必须引用 subquery 别名，而非裸 ORM 表（否则 CROSS JOIN → total=N×N）
    outer = compiled.split(") as anon_1")[-1]
    assert "anon_1.enabled" in compiled
    assert "anon_1.last_test_status" in compiled
    assert "system_gateway_models" not in outer


def test_registry_q_clause_includes_credential_name_exists() -> None:
    """q 筛选须匹配凭据展示名（team 凭据 EXISTS 子查询）。"""
    stmt = build_tenant_list_stmt(
        tenant_id=uuid.uuid4(),
        only_enabled=False,
        capability=None,
        provider=None,
        credential_id=None,
        exclude_user_scope_credentials=False,
        enabled=None,
        q="Acme Prod",
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
    )
    compiled = str(stmt.compile()).lower()
    assert "provider_credentials" in compiled
    assert "exists" in compiled
    assert "name" in compiled


def test_registry_q_clause_restricts_readable_team_credential_ids() -> None:
    cred_a = uuid.uuid4()
    cred_b = uuid.uuid4()
    stmt = build_tenant_list_stmt(
        tenant_id=uuid.uuid4(),
        only_enabled=False,
        capability=None,
        provider=None,
        credential_id=None,
        exclude_user_scope_credentials=False,
        enabled=None,
        q="secret",
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
        readable_team_credential_ids=(cred_a, cred_b),
    )
    compiled = str(stmt.compile()).lower()
    assert "provider_credentials" in compiled
    assert " in " in compiled


def test_registry_q_clause_skips_credential_exists_when_no_readable_ids() -> None:
    """无可见凭据时 q 不得通过 EXISTS 匹配他人凭据名。"""
    stmt = build_tenant_list_stmt(
        tenant_id=uuid.uuid4(),
        only_enabled=False,
        capability=None,
        provider=None,
        credential_id=None,
        exclude_user_scope_credentials=False,
        enabled=None,
        q="member-owned-secret",
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
        readable_team_credential_ids=(),
    )
    compiled = str(stmt.compile()).lower()
    assert "exists" not in compiled
    assert "provider_credentials" not in compiled


def test_system_registry_q_clause_includes_system_credential_name_exists() -> None:
    stmt = build_system_list_stmt(
        only_enabled=False,
        capability=None,
        provider=None,
        credential_id=None,
        enabled=None,
        q="platform-key",
        connectivity=ModelListConnectivityFilter.ALL,
        sort_field=ModelListSortField.NAME,
        order=ModelListSortOrder.ASC,
    )
    compiled = str(stmt.compile()).lower()
    assert "system_provider_credentials" in compiled
    assert "exists" in compiled
