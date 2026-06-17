"""Phase2：部署选定后的「成员 + 凭据 + 模型」平台预算预扣 / 结算。

在 LiteLLM ``async_pre_call_hook`` 内执行（与 ProviderPlan 同链路，先于上游预扣）：
读取 Router 注入的 ``gateway_user_id`` / ``gateway_credential_id`` / ``gateway_model_name``，
经存在性索引快路径排除无规则用户，命中后复用 ``budget_config_cache`` + ``BudgetService``
预扣；耗尽抛 :class:`BudgetExceededError`（HTTP 429，**不**触发 Router fallback）。

信任边界：限额只信服务端构建的 metadata / model_info，绝不读取客户端可控字段。
"""

from __future__ import annotations

from contextlib import suppress
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.budget_config_cache import get_cached_budget_by_plan
from domains.gateway.application.budget_service import (
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_TOTAL,
    BudgetService,
    BudgetUsageCoord,
    redis_credential_segment_for_budget,
    redis_model_segment_for_budget,
)
from domains.gateway.application.user_credential_budget_index import has_user_credential
from domains.gateway.domain.errors import BudgetExceededError
from domains.gateway.domain.period_reset_anchor import period_reset_anchor_from_row
from domains.gateway.domain.proxy_policy import (
    build_user_credential_budget_plan,
    first_present_limit,
)
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.budget import GatewayBudget

logger = get_logger(__name__)

_RESERVATIONS_META_KEY = "_gateway_user_cred_budget_reservations"
_PHASE2_PERIODS = (PERIOD_DAILY, PERIOD_MONTHLY, PERIOD_TOTAL)


def _to_uuid(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    with suppress(ValueError, TypeError):
        return uuid.UUID(str(value))
    return None


def _model_info(data: dict[str, Any]) -> dict[str, Any]:
    for container_key in ("litellm_params", "standard_logging_object"):
        container = data.get(container_key)
        if isinstance(container, dict):
            mi = container.get("model_info")
            if isinstance(mi, dict):
                return mi
    mi = data.get("model_info")
    return mi if isinstance(mi, dict) else {}


def _phase2_attribution(
    data: dict[str, Any],
) -> tuple[uuid.UUID | None, uuid.UUID | None, str | None, str | None]:
    """从服务端构建的 metadata / model_info 读取 Phase2 归因字段。"""
    raw_meta = data.get("metadata")
    metadata = raw_meta if isinstance(raw_meta, dict) else {}
    user_id = _to_uuid(metadata.get("gateway_user_id"))
    mi = _model_info(data)
    credential_id = _to_uuid(mi.get("gateway_credential_id"))
    raw_name = mi.get("gateway_model_name")
    gateway_model_name = str(raw_name) if raw_name else None
    scope = mi.get("gateway_credential_scope")
    scope_str = str(scope) if scope else None
    return user_id, credential_id, gateway_model_name, scope_str


async def maybe_reserve_user_credential_budget(
    data: dict[str, Any], *, estimate_tokens: int = 0
) -> None:
    """命中成员+凭据预算时预扣；耗尽抛 ``BudgetExceededError``。无规则零开销。"""
    user_id, credential_id, gateway_model_name, scope = _phase2_attribution(data)
    if user_id is None or credential_id is None:
        return
    # BYOK（个人凭据，scope=user）从不挂团队预算，直接跳过。
    if scope == "user":
        return
    # 存在性索引快路径：明确无规则则零开销返回。
    indexed = await has_user_credential(user_id, credential_id)
    if indexed is False:
        return

    plan = build_user_credential_budget_plan(
        user_id=user_id,
        credential_id=credential_id,
        gateway_model_name=gateway_model_name,
        periods=_PHASE2_PERIODS,
    )

    async def _loader() -> dict[Any, GatewayBudget]:
        from domains.gateway.infrastructure.repositories.budget_repository import (
            BudgetRepository,
        )
        from libs.db.database import get_session_context

        async with get_session_context() as session:
            return await BudgetRepository(session).get_many_by_plan(plan)

    budget_by_coord = await get_cached_budget_by_plan(plan, _loader)
    if not budget_by_coord:
        return

    budget = BudgetService()
    user_id_str = str(user_id)
    cred_seg = redis_credential_segment_for_budget(credential_id)

    check_items = []
    usage_coords: list[BudgetUsageCoord] = []
    for query in plan:
        config = budget_by_coord.get(
            (
                query.target_kind,
                query.target_id,
                query.period,
                query.model_name,
                credential_id,
                query.tenant_id,
            )
        )
        if config is None:
            continue
        coord = BudgetUsageCoord(
            target_kind="user",
            target_id=user_id_str,
            period=query.period,
            model_segment=redis_model_segment_for_budget(config.model_name),
            credential_segment=cred_seg,
            period_reset_anchor=config.period_reset_anchor,
        )
        check_items.append((query, config, coord))
        usage_coords.append(coord)

    if not check_items:
        return

    usage_by_coord = await budget.read_budget_usage_batch(usage_coords)

    reservations: list[dict[str, Any]] = []
    for query, config, coord in check_items:
        check = await budget.check_budget(
            target_kind="user",
            target_id=user_id_str,
            period=query.period,
            limit_usd=config.limit_usd,
            limit_tokens=config.limit_tokens,
            limit_requests=config.limit_requests,
            budget_model_name=config.model_name,
            credential_id=credential_id,
            prefetched_usage=usage_by_coord.get(coord),
            period_reset_anchor=config.period_reset_anchor,
        )
        if not check.allowed:
            await _release(reservations)
            raise BudgetExceededError(
                scope="user_credential",
                period=query.period,
                limit=float(
                    first_present_limit(
                        (config.limit_usd, config.limit_tokens, config.limit_requests)
                    )
                ),
                used=float(
                    check.used_usd
                    if check.reason == "usd"
                    else check.used_tokens
                    if check.reason == "tokens"
                    else check.used_requests
                ),
            )
        if (config.limit_requests is None or config.limit_requests <= 0) and (
            config.limit_tokens is None or config.limit_tokens <= 0 or estimate_tokens <= 0
        ):
            continue
        try:
            reserved_requests, reserved_tokens = await budget.reserve(
                target_kind="user",
                target_id=user_id_str,
                period=query.period,
                limit_requests=config.limit_requests,
                limit_tokens=config.limit_tokens,
                estimate_tokens=estimate_tokens,
                budget_model_name=config.model_name,
                credential_id=credential_id,
                period_reset_anchor=config.period_reset_anchor,
            )
        except Exception:
            await _release(reservations)
            raise
        if reserved_requests or reserved_tokens:
            reservations.append(
                {
                    "target_id": user_id_str,
                    "period": query.period,
                    "budget_model_name": config.model_name,
                    "credential_id": str(credential_id),
                    "reserved_requests": reserved_requests,
                    "reserved_tokens": reserved_tokens,
                    "period_timezone": config.period_reset_anchor.timezone,
                    "period_reset_minutes": config.period_reset_anchor.time_minutes,
                    "period_reset_day": config.period_reset_anchor.day_of_month,
                }
            )

    if reservations:
        meta = data.get("metadata")
        if not isinstance(meta, dict):
            meta = {}
            data["metadata"] = meta
        meta[_RESERVATIONS_META_KEY] = reservations


async def _release(
    reservations: list[dict[str, Any]],
    *,
    release_requests: bool = True,
    release_tokens: bool = True,
) -> None:
    if not reservations:
        return
    budget = BudgetService()
    for r in reservations:
        reserved_requests = int(r.get("reserved_requests") or 0) if release_requests else 0
        reserved_tokens = int(r.get("reserved_tokens") or 0) if release_tokens else 0
        if reserved_requests <= 0 and reserved_tokens <= 0:
            continue
        with suppress(Exception):
            anchor = period_reset_anchor_from_row(
                timezone=r.get("period_timezone"),
                time_minutes=r.get("period_reset_minutes"),
                day_of_month=r.get("period_reset_day"),
            )
            await budget.release(
                target_kind="user",
                target_id=r.get("target_id"),
                period=r["period"],
                budget_model_name=r.get("budget_model_name"),
                credential_id=_to_uuid(r.get("credential_id")),
                reserved_requests=reserved_requests,
                reserved_tokens=reserved_tokens,
                period_reset_anchor=anchor,
            )


async def release_user_credential_budget_from_metadata(metadata: dict[str, Any]) -> None:
    """失败回调：释放 Phase2 预扣的请求 / token 名额。"""
    raw = metadata.get(_RESERVATIONS_META_KEY)
    if isinstance(raw, list):
        await _release([r for r in raw if isinstance(r, dict)])


async def release_user_credential_budget_token_reservations_from_metadata(
    metadata: dict[str, Any],
    *,
    request_id: str | None = None,
) -> None:
    """成功回调：释放 token 估算预扣，保留 request 预扣作为请求计数。"""
    raw = metadata.get(_RESERVATIONS_META_KEY)
    if not isinstance(raw, list):
        return
    if request_id:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()
        acquired = await client.set(
            f"{_PHASE2_TOKEN_RELEASED_PREFIX}{request_id}",
            "1",
            nx=True,
            ex=_PHASE2_SETTLED_TTL,
        )
        if not acquired:
            return
    await _release(
        [r for r in raw if isinstance(r, dict)],
        release_requests=False,
        release_tokens=True,
    )


_PHASE2_SETTLED_PREFIX = "gateway:budget:uc_settled:"
_PHASE2_TOKEN_RELEASED_PREFIX = "gateway:budget:uc_token_released:"
_PHASE2_SETTLED_TTL = 86400


async def commit_user_credential_budget(
    *,
    user_id: uuid.UUID | None,
    credential_id: uuid.UUID | None,
    gateway_model_name: str | None,
    cost_usd: Decimal,
    total_tokens: int,
    request_id: str | None = None,
) -> None:
    """成功回调：把真实成本/ token 累加到成员+凭据(+模型) 预算桶。

    经存在性索引网关，仅对确有规则的用户写入，避免普通请求无谓 Redis 写；
    按 ``request_id`` 幂等，避免流式 / 多回调重复累加。
    """
    if user_id is None or credential_id is None or (cost_usd <= 0 and total_tokens <= 0):
        return
    if (await has_user_credential(user_id, credential_id)) is not True:
        return
    if request_id:
        from libs.db.redis import get_redis_client

        client = await get_redis_client()
        acquired = await client.set(
            f"{_PHASE2_SETTLED_PREFIX}{request_id}", "1", nx=True, ex=_PHASE2_SETTLED_TTL
        )
        if not acquired:
            return

    plan = build_user_credential_budget_plan(
        user_id=user_id,
        credential_id=credential_id,
        gateway_model_name=gateway_model_name,
        periods=_PHASE2_PERIODS,
    )

    async def _loader() -> dict[Any, GatewayBudget]:
        from domains.gateway.infrastructure.repositories.budget_repository import (
            BudgetRepository,
        )
        from libs.db.database import get_session_context

        async with get_session_context() as session:
            return await BudgetRepository(session).get_many_by_plan(plan)

    budget_by_coord = await get_cached_budget_by_plan(plan, _loader)
    if not budget_by_coord:
        return

    budget = BudgetService()
    user_id_str = str(user_id)
    for query in plan:
        config = budget_by_coord.get(
            (
                query.target_kind,
                query.target_id,
                query.period,
                query.model_name,
                credential_id,
                query.tenant_id,
            )
        )
        if config is None:
            continue
        with suppress(Exception):
            await budget.commit(
                target_kind="user",
                target_id=user_id_str,
                period=query.period,
                delta_cost=cost_usd,
                delta_tokens=total_tokens,
                budget_model_name=config.model_name,
                credential_id=credential_id,
                period_reset_anchor=config.period_reset_anchor,
            )


__all__ = [
    "commit_user_credential_budget",
    "maybe_reserve_user_credential_budget",
    "release_user_credential_budget_from_metadata",
    "release_user_credential_budget_token_reservations_from_metadata",
]
