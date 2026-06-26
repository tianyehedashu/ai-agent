"""成员总量/模型护栏 Redis 用量桶按团队隔离单测。"""

from __future__ import annotations

from decimal import Decimal
import uuid

import pytest

from domains.gateway.application.budget_service import (
    BudgetService,
    BudgetUsageCoord,
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


def test_custom_anchor_uses_ws_suffix_in_bucket_key() -> None:
    from datetime import UTC, datetime

    from domains.gateway.domain.period_reset_anchor import PeriodResetAnchor

    anchor = PeriodResetAnchor(timezone="Asia/Shanghai", time_minutes=9 * 60, day_of_month=1)
    now = datetime(2026, 6, 15, 8, 30, tzinfo=UTC)
    key = _bucket_key("tenant", "tid", "daily", period_reset_anchor=anchor, now=now)
    assert ":ws:" in key
    default_key = _bucket_key("tenant", "tid", "daily", now=now)
    assert ":ws:" not in default_key


@pytest.mark.asyncio
async def test_tenant_usage_batch_sums_primary_and_legacy_team_keys(monkeypatch) -> None:
    class _Pipeline:
        def __init__(self) -> None:
            self.hmget_calls: list[tuple[str, list[str]]] = []

        def hmget(self, key: str, fields: list[str]) -> None:
            self.hmget_calls.append((key, fields))

        async def execute(self) -> list[list[bytes]]:
            return [
                [b"1.25", b"10", b"2", b"0"],
                [b"2.75", b"5", b"3", b"0"],
            ]

    class _Redis:
        def __init__(self) -> None:
            self.pipeline_instance = _Pipeline()

        def pipeline(self) -> _Pipeline:
            return self.pipeline_instance

    redis = _Redis()

    async def _redis_client() -> _Redis:
        return redis

    import domains.gateway.application.budget_service as mod

    monkeypatch.setattr(mod, "get_redis_client", _redis_client)

    coord = BudgetUsageCoord(
        target_kind="tenant",
        target_id="tenant-1",
        period="daily",
        model_segment=None,
    )
    usage = await BudgetService().read_budget_usage_batch([coord])

    assert usage[coord] == (Decimal("4.00"), 15, 5, 0)
    assert len(redis.pipeline_instance.hmget_calls) == 2
