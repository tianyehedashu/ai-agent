"""UsageAxis → SQL WHERE 子句单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.usage.usage_axis import UsageAxis
from domains.gateway.infrastructure.repositories.usage_axis_sql import (
    usage_axis_base_clauses,
    usage_axis_count_disjuncts,
    usage_axis_user_visibility_disjuncts,
)


def _compile(clause: object) -> str:
    return str(clause.compile(compile_kwargs={"literal_binds": True}))


def test_user_axis_uses_non_correlated_vkey_in_subquery() -> None:
    uid = uuid.uuid4()
    clauses = usage_axis_base_clauses(UsageAxis.user(uid))
    assert len(clauses) == 1
    compiled = _compile(clauses[0])
    assert "gateway_virtual_keys" in compiled
    assert "created_by_user_id" in compiled
    assert "EXISTS" not in compiled.upper()
    assert " IN (" in compiled.upper() or " IN " in compiled.upper()


def test_user_axis_disjuncts_are_mutually_exclusive_on_vkey_nullability() -> None:
    uid = uuid.uuid4()
    platform_inbound, vkey_attributed = usage_axis_user_visibility_disjuncts(uid)
    platform_sql = _compile(platform_inbound)
    vkey_sql = _compile(vkey_attributed)
    assert "vkey_id IS NULL" in platform_sql
    assert "vkey_id IS NOT NULL" in vkey_sql


def test_user_axis_count_disjuncts_index_is_zero() -> None:
    uid = uuid.uuid4()
    disjuncts, idx = usage_axis_count_disjuncts(UsageAxis.user(uid))
    assert idx == 0
    assert len(disjuncts) == 2


def test_workspace_member_axis_count_disjuncts_index_is_one() -> None:
    tid = uuid.uuid4()
    uid = uuid.uuid4()
    disjuncts, idx = usage_axis_count_disjuncts(
        UsageAxis.workspace(tid, member_user_id=uid),
    )
    assert idx == 1
    assert len(disjuncts) == 2
    platform_sql = _compile(disjuncts[0])
    vkey_sql = _compile(disjuncts[1])
    assert "vkey_id IS NULL" in platform_sql
    assert "vkey_id IS NOT NULL" in vkey_sql
    assert "gateway_virtual_keys.tenant_id" in vkey_sql


def test_workspace_axis_without_member_has_team_only() -> None:
    tid = uuid.uuid4()
    clauses = usage_axis_base_clauses(UsageAxis.workspace(tid))
    assert len(clauses) == 1
    assert usage_axis_count_disjuncts(UsageAxis.workspace(tid)) is None


def test_platform_axis_has_no_count_disjuncts() -> None:
    assert usage_axis_base_clauses(UsageAxis.platform()) == []
    assert usage_axis_count_disjuncts(UsageAxis.platform()) is None
