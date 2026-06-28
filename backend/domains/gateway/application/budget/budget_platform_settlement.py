"""平台预算 Redis 结算：仅对存在规则且命中配置缓存的坐标 commit（含周期锚点）。"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.proxy.proxy_context import BudgetAnchorCoord
from domains.gateway.domain.proxy.proxy_policy import (
    BudgetCheckQuery,
    build_budget_check_plan,
)
from domains.gateway.domain.quota.period_reset_anchor import (
    PeriodResetAnchor,
    normalize_period_reset_anchor,
)
from utils.logging import get_logger

from .budget_config_cache import (
    BudgetConfigRow,
    get_cached_budget_by_plan,
)
from .budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_TOTAL,
    BudgetService,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from domains.gateway.infrastructure.models.budget import GatewayBudget

logger = get_logger(__name__)

_Coord = BudgetAnchorCoord


def budget_anchor_coord_from_query(query: BudgetCheckQuery) -> _Coord:
    return (
        query.target_kind,
        query.target_id,
        query.period,
        query.model_name,
        query.credential_id,
        query.tenant_id,
    )


def resolve_budget_commit_anchor(
    coord: _Coord,
    *,
    config_anchor: PeriodResetAnchor,
    pinned_anchors: dict[_Coord, PeriodResetAnchor] | None,
) -> PeriodResetAnchor:
    """preflight 已 pin 的坐标优先，避免锚点 mid-flight 变更导致 reserve/commit 分桶。"""
    if pinned_anchors is None:
        return config_anchor
    return pinned_anchors.get(coord, config_anchor)


def serialize_budget_anchor_pins(
    pins: dict[_Coord, PeriodResetAnchor],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for coord, anchor in pins.items():
        target_kind, target_id, period, model_name, credential_id, tenant_id = coord
        rows.append(
            {
                "target_kind": target_kind,
                "target_id": str(target_id) if target_id is not None else None,
                "period": period,
                "model_name": model_name,
                "credential_id": str(credential_id) if credential_id is not None else None,
                "tenant_id": str(tenant_id) if tenant_id is not None else None,
                "timezone": anchor.timezone,
                "time_minutes": anchor.time_minutes,
                "day_of_month": anchor.day_of_month,
            }
        )
    return rows


def deserialize_budget_anchor_pins(raw: object) -> dict[_Coord, PeriodResetAnchor]:
    if not isinstance(raw, list):
        return {}
    pins: dict[_Coord, PeriodResetAnchor] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        target_kind = item.get("target_kind")
        period = item.get("period")
        if not isinstance(target_kind, str) or not isinstance(period, str):
            continue
        target_id = _parse_uuid(item.get("target_id"))
        credential_id = _parse_uuid(item.get("credential_id"))
        tenant_id = _parse_uuid(item.get("tenant_id"))
        model_name = item.get("model_name")
        model_name_str = model_name if isinstance(model_name, str) else None
        anchor = normalize_period_reset_anchor(
            timezone=item.get("timezone") if isinstance(item.get("timezone"), str) else None,
            time_minutes=item.get("time_minutes")
            if isinstance(item.get("time_minutes"), int)
            else None,
            day_of_month=item.get("day_of_month")
            if isinstance(item.get("day_of_month"), int)
            else None,
        )
        pins[
            (
                target_kind,
                target_id,
                period,
                model_name_str,
                credential_id,
                tenant_id,
            )
        ] = anchor
    return pins


def _parse_uuid(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


async def commit_cached_platform_budgets(
    budget: BudgetService,
    *,
    scope_items: list[tuple[str, uuid.UUID | None]],
    periods: tuple[str, ...],
    budget_model: str | None,
    billing_team_id: uuid.UUID | None,
    delta_cost: Decimal,
    delta_tokens: int,
    loader: Callable[[tuple[BudgetCheckQuery, ...]], Awaitable[dict[_Coord, GatewayBudget]]],
    pinned_anchors: dict[_Coord, PeriodResetAnchor] | None = None,
    delta_images: int = 0,
) -> set[_Coord]:
    """按配置缓存批量结算；无规则坐标不写 Redis。"""
    committed_coords: set[_Coord] = set()
    plan_parts: list[BudgetCheckQuery] = []
    for target_kind, target_id in scope_items:
        if target_id is None:
            continue
        tenant_scope = billing_team_id if target_kind == "user" else None
        plan_parts.extend(
            build_budget_check_plan(
                targets=[(target_kind, target_id)],
                periods=periods,
                request_model=budget_model,
                tenant_id=tenant_scope,
            )
        )

    if not plan_parts:
        return committed_coords

    plan = tuple(dict.fromkeys(plan_parts))

    async def _load() -> dict[_Coord, GatewayBudget]:
        return await loader(plan)

    budget_by_coord = await get_cached_budget_by_plan(plan, _load)
    if not budget_by_coord:
        return committed_coords

    for query in plan:
        coord = budget_anchor_coord_from_query(query)
        config: BudgetConfigRow | None = budget_by_coord.get(coord)
        if config is None:
            continue
        target_id_str = str(query.target_id) if query.target_id is not None else None
        anchor = resolve_budget_commit_anchor(
            coord,
            config_anchor=config.period_reset_anchor,
            pinned_anchors=pinned_anchors,
        )
        try:
            # 仅对配置了 ``limit_images`` 的预算行校正图片张数；其余行不写 images 维度
            row_delta_images = delta_images if config.limit_images is not None else 0
            await budget.commit(
                target_kind=query.target_kind,
                target_id=target_id_str,
                period=query.period,
                delta_cost=delta_cost,
                delta_tokens=delta_tokens,
                budget_model_name=config.model_name,
                credential_id=query.credential_id,
                tenant_id=query.tenant_id,
                period_reset_anchor=anchor,
                delta_images=row_delta_images,
            )
            committed_coords.add(coord)
        except Exception:
            logger.warning(
                "Platform budget Redis commit failed kind=%s period=%s target=%s",
                query.target_kind,
                query.period,
                target_id_str,
                exc_info=True,
            )
    return committed_coords


DEFAULT_PLATFORM_PERIODS = (PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL)


__all__ = [
    "DEFAULT_PLATFORM_PERIODS",
    "budget_anchor_coord_from_query",
    "commit_cached_platform_budgets",
    "deserialize_budget_anchor_pins",
    "resolve_budget_commit_anchor",
    "serialize_budget_anchor_pins",
]
