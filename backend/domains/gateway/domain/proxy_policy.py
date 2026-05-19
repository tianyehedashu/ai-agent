"""Gateway 代理调用的纯领域策略。

本模块只处理不变量与策略判定，不接触 ORM、Redis、LiteLLM 或 HTTP。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.errors import (
    CapabilityNotAllowedError,
    ModelNotAllowedError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from domains.gateway.domain.types import GatewayCapability


BudgetScopeTarget = tuple[str, uuid.UUID | None]
BudgetReservation = tuple[str, str | None, str, str | None]


@dataclass(frozen=True)
class BudgetCheckQuery:
    """单次预算扫描所需的查询坐标。

    Attributes:
        scope: ``team`` / ``user`` / ``key`` 之一（与 ``BudgetScope`` 写入维度对齐，
            排除了 ``system``，因为系统级预算不绑定具体调用上下文）。
        scope_id: 对应 scope 的主键；保证非空，由 ``build_budget_check_plan`` 过滤。
        period: ``daily`` / ``monthly`` / ``total``。
        model_name: ``None`` = 全模型汇总行（``gateway_budgets.model_name IS NULL``），
            其它值表示模型级专属预算行。
    """

    scope: str
    scope_id: uuid.UUID
    period: str
    model_name: str | None


def build_budget_check_plan(
    *,
    targets: tuple[BudgetScopeTarget, ...],
    periods: tuple[str, ...],
    request_model: str | None,
) -> tuple[BudgetCheckQuery, ...]:
    """生成单次代理调用应扫描的全部预算查询坐标（纯函数）。

    每个非空 scope target × period × ``budget_model_keys(request_model)``。
    顺序保证「先汇总行（``None``），再模型专属行」，与历史 ``_check_budget``
    行为一致；调用方按此顺序遇到耗尽即抛错。
    """
    queries: list[BudgetCheckQuery] = []
    for scope, scope_id in targets:
        if scope_id is None:
            continue
        for period in periods:
            for model_key in budget_model_keys(request_model):
                queries.append(
                    BudgetCheckQuery(
                        scope=scope,
                        scope_id=scope_id,
                        period=period,
                        model_name=model_key,
                    )
                )
    return tuple(queries)


def assert_model_allowed(model: str, allowed_models: tuple[str, ...]) -> None:
    """校验客户端请求模型是否在调用令牌白名单内。"""
    if allowed_models and model not in allowed_models:
        raise ModelNotAllowedError(model)


def assert_capability_allowed(
    capability: GatewayCapability,
    allowed_capabilities: tuple[GatewayCapability, ...],
) -> None:
    """校验当前 HTTP 调用面是否被调用令牌允许。"""
    if allowed_capabilities and capability not in allowed_capabilities:
        raise CapabilityNotAllowedError(capability.value)


def assert_registered_model_capability(
    *,
    model_name: str,
    requested: GatewayCapability,
    registered_capability: str,
    via_route: bool,
) -> None:
    """注册模型/路由主模型的 capability 必须匹配当前 HTTP 入口。"""
    registered = registered_capability.strip().lower()
    if registered == requested.value:
        return
    label = "虚拟路由" if via_route else "模型"
    raise CapabilityNotAllowedError(
        requested.value,
        message=(
            f"{label} {model_name!r} 的主调用面为 {registered!r}，"
            f"当前接口需要 {requested.value!r}（请使用对应的 OpenAI 兼容端点）"
        ),
    )


def budget_scope_targets(
    *,
    team_id: uuid.UUID,
    user_id: uuid.UUID | None,
    vkey_id: uuid.UUID | None,
) -> tuple[BudgetScopeTarget, ...]:
    """一次代理调用需要检查/结算的预算归属层级。"""
    scopes: list[BudgetScopeTarget] = [("team", team_id)]
    if user_id is not None:
        scopes.append(("user", user_id))
    if vkey_id is not None:
        scopes.append(("key", vkey_id))
    return tuple(scopes)


def budget_model_keys(model_name: str | None) -> tuple[str | None, ...]:
    """预算需要同时写全模型汇总行与可选模型专属行。"""
    if model_name:
        return (None, model_name)
    return (None,)


def rate_limit_target(
    *,
    vkey_id: uuid.UUID | None,
    platform_api_key_grant_id: uuid.UUID | None,
    platform_api_key_id: uuid.UUID | None,
) -> tuple[str, str | None] | None:
    """返回限流计数目标；无可识别调用令牌时不做 token 级限流。"""
    if vkey_id is not None:
        return ("vkey", str(vkey_id))
    api_key_scope_id = platform_api_key_grant_id or platform_api_key_id
    if api_key_scope_id is None:
        return None
    return ("platform_api_key_grant", str(api_key_scope_id))


def first_present_limit(values: Iterable[object | None]) -> object:
    """预算错误文案使用的首个非空 limit 值。"""
    for value in values:
        if value is not None:
            return value
    return 0


__all__ = [
    "BudgetCheckQuery",
    "BudgetReservation",
    "BudgetScopeTarget",
    "assert_capability_allowed",
    "assert_model_allowed",
    "assert_registered_model_capability",
    "budget_model_keys",
    "budget_scope_targets",
    "build_budget_check_plan",
    "first_present_limit",
    "rate_limit_target",
]
