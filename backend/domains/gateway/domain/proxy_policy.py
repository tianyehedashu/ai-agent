"""Gateway 代理调用的纯领域策略。

本模块只处理不变量与策略判定，不接触 ORM、Redis、LiteLLM 或 HTTP。
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING
import uuid

from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
)
from domains.gateway.domain.errors import (
    CapabilityNotAllowedError,
    ModelNotAllowedError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from domains.gateway.domain.types import GatewayCapability


BudgetTarget = tuple[str, uuid.UUID | None]


@dataclass(frozen=True)
class BudgetReservation:
    """预算预扣句柄（请求数 / token 估算）。"""

    target_kind: str
    target_id: str | None
    period: str
    budget_model_name: str | None
    reserved_requests: int = 0
    reserved_tokens: int = 0
    credential_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    period_reset_anchor: PeriodResetAnchor = DEFAULT_PERIOD_RESET_ANCHOR


@dataclass(frozen=True)
class BudgetCheckQuery:
    """单次预算扫描所需的查询坐标。

    Attributes:
        target_kind: ``system`` / ``tenant`` / ``user`` / ``key``。
        target_id: 对应 target 的主键；``system`` 为 ``None``。
        period: ``daily`` / ``monthly`` / ``total``。
        model_name: ``None`` = 全模型汇总行（``gateway_budgets.model_name IS NULL``），
            其它值表示模型级专属预算行。
        credential_id: ``None`` = 命中 ``credential_id IS NULL`` 的汇总/模型行（Phase1）；
            非空 = 成员+凭据(+模型) 专属预算行（Phase2，部署选定后归因）。
        tenant_id: 仅 ``target_kind=user`` 且 ``credential_id IS NULL`` 的成员总量/模型护栏行非空，
            表示按团队隔离的归属；命中 ``gateway_budgets.tenant_id`` 精确匹配（含 ``IS NULL``）。
    """

    target_kind: str
    target_id: uuid.UUID | None
    period: str
    model_name: str | None
    credential_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None


def build_budget_check_plan(
    *,
    targets: tuple[BudgetTarget, ...],
    periods: tuple[str, ...],
    request_model: str | None,
    tenant_id: uuid.UUID | None = None,
) -> tuple[BudgetCheckQuery, ...]:
    """生成单次代理调用应扫描的全部预算查询坐标（纯函数）。

    每个非空 target × period × ``budget_model_keys(request_model)``。
    顺序保证「先汇总行（``None``），再模型专属行」，与历史 ``_check_budget``
    行为一致；调用方按此顺序遇到耗尽即抛错。

    ``tenant_id`` 仅施加于 ``user`` 维度（成员总量/模型护栏按团队隔离）；
    其余维度恒以 ``tenant_id=None`` 匹配。
    """
    queries: list[BudgetCheckQuery] = []
    for target_kind, target_id in targets:
        if target_id is None and target_kind != "system":
            continue
        query_tenant = tenant_id if target_kind == "user" else None
        for period in periods:
            for model_key in budget_model_keys(request_model):
                queries.append(
                    BudgetCheckQuery(
                        target_kind=target_kind,
                        target_id=target_id,
                        period=period,
                        model_name=model_key,
                        tenant_id=query_tenant,
                    )
                )
    return tuple(queries)


def build_user_credential_budget_plan(
    *,
    user_id: uuid.UUID,
    credential_id: uuid.UUID,
    gateway_model_name: str | None,
    periods: tuple[str, ...],
) -> tuple[BudgetCheckQuery, ...]:
    """Phase2 成员+凭据(+模型) 预算扫描坐标（部署选定后）。

    与 Phase1 隔离：仅 ``target_kind=user`` + 指定 ``credential_id``；
    ``gateway_model_name`` 为部署实际虚拟别名（非路由名），同时扫描凭据汇总行
    （``model_name IS NULL``）与该别名专属行。
    """
    queries: list[BudgetCheckQuery] = []
    for period in periods:
        for model_key in budget_model_keys(gateway_model_name):
            queries.append(
                BudgetCheckQuery(
                    target_kind="user",
                    target_id=user_id,
                    period=period,
                    model_name=model_key,
                    credential_id=credential_id,
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


def budget_targets(
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    vkey_id: uuid.UUID | None,
) -> tuple[BudgetTarget, ...]:
    """一次代理调用需要检查/结算的预算归属层级（不含 system）。"""
    targets: list[BudgetTarget] = [("tenant", tenant_id)]
    if user_id is not None:
        targets.append(("user", user_id))
    if vkey_id is not None:
        targets.append(("key", vkey_id))
    return tuple(targets)


def proxy_budget_targets(
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    vkey_id: uuid.UUID | None,
) -> tuple[BudgetTarget, ...]:
    """代理热路径预算扫描：全局 system + tenant/user/key。"""
    return (
        ("system", None),
        *budget_targets(
            tenant_id=tenant_id,
            user_id=user_id,
            vkey_id=vkey_id,
        ),
    )


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


def allows_unregistered_gateway_model(
    *,
    vkey_is_system: bool | None,
    disable_internal_direct_litellm: bool,
) -> bool:
    """system vkey 内部桥接允许未注册 model 直连 LiteLLM；其它入口须先解析 Gateway 模型。"""
    if disable_internal_direct_litellm:
        return False
    return vkey_is_system is True


_ROUTER_MODEL_MISS_MARKERS: tuple[str, ...] = (
    "no deployments available",
    "no healthy deployments",
    "no deployment",
    "no models available",
    "unable to find deployment",
    "model not found",
    "could not find model",
)


def is_router_deployment_cooldown(exc: Exception) -> bool:
    """LiteLLM Router 全部 deployment 处于 cooldown（常见原因：上游 429 限流）。"""
    if type(exc).__name__ in ("RouterRateLimitError", "RouterRateLimitErrorBasic"):
        return True
    message = str(exc).lower()
    return "no deployments available" in message and "try again in" in message


def router_cooldown_retry_after(exc: Exception) -> int | None:
    """从 Router cooldown 异常提取 ``Retry-After`` 秒数。"""
    cooldown_time = getattr(exc, "cooldown_time", None)
    if isinstance(cooldown_time, (int, float)) and cooldown_time > 0:
        return int(cooldown_time)
    match = re.search(r"try again in (\d+) seconds?", str(exc), flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def upstream_exception_http_status(exc: Exception) -> int | None:
    """LiteLLM / OpenAI SDK 异常上的 ``status_code``（若存在）。"""
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    return None


def upstream_exception_retry_after(exc: Exception) -> int | None:
    """从上游异常 response headers 提取 ``Retry-After``。"""
    response = getattr(exc, "response", None)
    if response is None:
        return None
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("retry-after")
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def is_router_model_miss(exc: Exception) -> bool:
    """LiteLLM Router 找不到 deployment 时的异常文案识别（compat 错误映射兜底）。"""
    if is_router_deployment_cooldown(exc):
        return False
    message = str(exc).lower()
    return any(marker in message for marker in _ROUTER_MODEL_MISS_MARKERS)


def is_router_unavailable_wrapper(exc: Exception) -> bool:
    """Router 聚合失败（无 healthy deployment / cooldown），非上游直出异常。"""
    return is_router_deployment_cooldown(exc) or is_router_model_miss(exc)


_ROUTER_WRAPPER_TYPE_NAMES: frozenset[str] = frozenset(
    {
        "BadRequestError",
        "RouterRateLimitError",
        "RouterRateLimitErrorBasic",
    }
)


def iter_proxy_exception_chain(exc: BaseException) -> list[BaseException]:
    """广度优先遍历异常链（``__cause__`` / ``__context__`` / ``ExceptionGroup``）。"""
    ordered: list[BaseException] = []
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        current = stack.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        ordered.append(current)
        cause = current.__cause__
        if cause is not None:
            stack.append(cause)
        context = current.__context__
        if context is not None and context is not cause:
            stack.append(context)
        nested = getattr(current, "exceptions", None)
        if nested:
            stack.extend(nested)
    return ordered


def _upstream_exception_rank(exc: Exception) -> int:
    status = upstream_exception_http_status(exc)
    if status in (401, 403):
        return 100
    if status == 429:
        return 90
    if status is not None and status >= 500:
        return 80
    if status is not None:
        return 70
    if type(exc).__name__ == "HTTPStatusError":
        return 60
    name = type(exc).__name__
    if name.endswith("Error") and name not in _ROUTER_WRAPPER_TYPE_NAMES:
        return 50
    return 0


def resolve_upstream_proxy_exception(exc: Exception) -> Exception | None:
    """从 Router 包装异常链中提取最应透传给客户端的上游异常。"""
    best: Exception | None = None
    best_rank = 0
    for item in iter_proxy_exception_chain(exc):
        if not isinstance(item, Exception):
            continue
        if item is exc and is_router_unavailable_wrapper(item):
            continue
        if is_router_unavailable_wrapper(item):
            continue
        rank = _upstream_exception_rank(item)
        if rank > best_rank:
            best_rank = rank
            best = item
    return best


def is_reportable_upstream_proxy_exception(exc: Exception) -> bool:
    """是否应将异常作为上游失败透传给客户端（排除 Router 包装与本地 ValueError 等）。"""
    if is_router_unavailable_wrapper(exc):
        return False
    if upstream_exception_http_status(exc) is not None:
        return True
    if type(exc).__name__ == "HTTPStatusError":
        return True
    module = type(exc).__module__ or ""
    if module.startswith("litellm"):
        return type(exc).__name__ not in _ROUTER_WRAPPER_TYPE_NAMES
    return False


__all__ = [
    "BudgetCheckQuery",
    "BudgetReservation",
    "BudgetTarget",
    "allows_unregistered_gateway_model",
    "assert_capability_allowed",
    "assert_model_allowed",
    "assert_registered_model_capability",
    "budget_model_keys",
    "budget_targets",
    "build_budget_check_plan",
    "first_present_limit",
    "is_reportable_upstream_proxy_exception",
    "is_router_deployment_cooldown",
    "is_router_model_miss",
    "is_router_unavailable_wrapper",
    "iter_proxy_exception_chain",
    "proxy_budget_targets",
    "rate_limit_target",
    "resolve_upstream_proxy_exception",
    "router_cooldown_retry_after",
    "upstream_exception_http_status",
    "upstream_exception_retry_after",
]
