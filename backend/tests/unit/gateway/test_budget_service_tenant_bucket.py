"""成员总量/模型护栏 Redis 用量桶按团队隔离单测。"""

from __future__ import annotations

import uuid

from domains.gateway.application.budget_service import (
    _bucket_key,
    redis_tenant_segment_for_budget,
)


def test_user_bucket_key_differs_by_tenant_segment() -> None:
    """同一成员、同一周期，不同团队的护栏桶 key 必须不同。"""
    user_id = str(uuid.uuid4())
    team_a = uuid.uuid4()
    team_b = uuid.uuid4()
    key_a = _bucket_key(
        "user", user_id, "monthly", tenant_segment=redis_tenant_segment_for_budget(team_a)
    )
    key_b = _bucket_key(
        "user", user_id, "monthly", tenant_segment=redis_tenant_segment_for_budget(team_b)
    )
    assert key_a != key_b
    assert ":t:" in key_a


def test_non_user_bucket_key_unchanged_without_tenant_segment() -> None:
    """tenant/system/key 维度不带 tenant 段，key 形态与历史一致（无 :t:）。"""
    team_id = str(uuid.uuid4())
    key = _bucket_key("tenant", team_id, "monthly")
    assert ":t:" not in key
