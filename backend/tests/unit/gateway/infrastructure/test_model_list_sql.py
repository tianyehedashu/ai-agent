"""model_list_sql 聚合 SQL 回归：connectivity_summary 不得与子查询笛卡尔积。"""

from __future__ import annotations

from domains.gateway.domain.policies.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
)
from domains.gateway.infrastructure.repositories.model_list_sql import (
    _summary_select,
    build_system_list_stmt,
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
