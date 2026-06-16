"""上游 ProviderPlan 查找优先级（纯规则，无 I/O）。"""

from __future__ import annotations


def provider_plan_match_rank(
    *,
    plan_real_model: str | None,
    lookup_real_model: str,
) -> int:
    """越小越优先：0 精确匹配，1 凭据级通配（``real_model IS NULL``）。"""
    if plan_real_model == lookup_real_model:
        return 0
    if plan_real_model is None:
        return 1
    return 2


__all__ = ["provider_plan_match_rank"]
