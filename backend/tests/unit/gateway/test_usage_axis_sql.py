"""UsageAxis → SQL WHERE 子句单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.usage_axis import UsageAxis
from domains.gateway.infrastructure.repositories.usage_axis_sql import usage_axis_base_clauses


def test_user_axis_matches_vkey_ownership_not_only_user_id_column() -> None:
    uid = uuid.uuid4()
    clauses = usage_axis_base_clauses(UsageAxis.user(uid))
    assert len(clauses) == 1
    compiled = str(clauses[0].compile(compile_kwargs={"literal_binds": True}))
    assert "gateway_virtual_keys" in compiled
    assert "created_by_user_id" in compiled


def test_workspace_axis_without_member_has_team_only() -> None:
    tid = uuid.uuid4()
    clauses = usage_axis_base_clauses(UsageAxis.workspace(tid))
    assert len(clauses) == 1
