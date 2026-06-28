"""Gateway 预算管理面：列表过滤与 target 归属判定（纯函数）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, TypeVar

from domains.gateway.domain.types import BudgetScope

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

T = TypeVar("T", bound="BudgetRowLike")


class BudgetRowLike(Protocol):
    target_kind: str
    model_name: str | None


@dataclass(frozen=True)
class BudgetListFilters:
    target_kind: str | None
    model_name: str | None


@dataclass(frozen=True)
class AdminBudgetFetchPlan:
    fetch_tenant: bool
    fetch_user: bool
    fetch_key: bool
    fetch_system: bool


@dataclass(frozen=True)
class BudgetTeamContext:
    tenant_id: UUID
    member_user_ids: frozenset[UUID]
    is_platform_admin: bool


def normalize_budget_list_filters(
    target_kind: str | None,
    model_name: str | None,
) -> BudgetListFilters:
    normalized_model = (model_name or "").strip() or None
    return BudgetListFilters(target_kind=target_kind, model_name=normalized_model)


def plan_admin_budget_fetch(
    *,
    target_kind: str | None,
    include_system: bool,
) -> AdminBudgetFetchPlan:
    fetch_all = target_kind is None
    return AdminBudgetFetchPlan(
        fetch_tenant=fetch_all or target_kind == BudgetScope.TENANT.value,
        fetch_user=fetch_all or target_kind == BudgetScope.USER.value,
        fetch_key=fetch_all or target_kind == BudgetScope.KEY.value,
        fetch_system=include_system and (fetch_all or target_kind == BudgetScope.SYSTEM.value),
    )


def filter_budget_rows(
    rows: Iterable[T],
    filters: BudgetListFilters,
) -> list[T]:
    result = list(rows)
    if filters.model_name is not None:
        result = [row for row in result if row.model_name == filters.model_name]
    if filters.target_kind is not None:
        result = [row for row in result if row.target_kind == filters.target_kind]
    return result


def budget_target_allowed(
    target_kind: str,
    target_id: UUID | None,
    ctx: BudgetTeamContext,
    *,
    key_belongs_to_team: bool | None = None,
) -> bool:
    if target_kind == BudgetScope.TENANT.value:
        return target_id == ctx.tenant_id

    if target_kind == BudgetScope.USER.value:
        if target_id is None:
            return False
        return target_id in ctx.member_user_ids

    if target_kind == BudgetScope.KEY.value:
        if target_id is None:
            return False
        return key_belongs_to_team is True

    if target_kind == BudgetScope.SYSTEM.value:
        return ctx.is_platform_admin

    return False


__all__ = [
    "AdminBudgetFetchPlan",
    "BudgetListFilters",
    "BudgetRowLike",
    "BudgetTeamContext",
    "budget_target_allowed",
    "filter_budget_rows",
    "normalize_budget_list_filters",
    "plan_admin_budget_fetch",
]
