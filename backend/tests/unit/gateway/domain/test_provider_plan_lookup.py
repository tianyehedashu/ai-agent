"""ProviderPlan 查找优先级单测。"""

from __future__ import annotations

from domains.gateway.domain.provider_plan_lookup import provider_plan_match_rank


def test_exact_match_ranks_before_wildcard() -> None:
    assert provider_plan_match_rank(
        plan_real_model="volcengine/doubao-lite",
        lookup_real_model="volcengine/doubao-lite",
    ) < provider_plan_match_rank(
        plan_real_model=None,
        lookup_real_model="volcengine/doubao-lite",
    )
