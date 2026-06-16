"""ProviderPlanGuard - 上游厂商套餐 pre-call 校验

在 LiteLLM Router 选中某个 deployment 后、真正打上游前，根据 ``model_info`` 中
携带的 ``gateway_credential_id`` + ``litellm_params.model`` 解析活跃 ProviderPlan
并对其下所有 quota 桶做检查 + 预扣。任一桶耗尽抛 ``ProviderPlanExhaustedError``
让 Router 触发自带 cooldown / fallback；调用方一般不会直接看到该错误。

注：guard 只与 ``QuotaPlanService`` + ``ProviderPlanRepository`` 协作，
不接触 ``EntitlementPlan`` 与 ``GatewayBudget``，与 ``EntitlementGuard`` 严格分离。
"""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.provider_plan_config_cache import (
    ProviderPlanConfigSnapshot,
    get_cached_active_provider_plan,
    plan_quota_specs_from_config,
    provider_plan_config_from_orm,
)
from domains.gateway.domain.errors import ProviderPlanExhaustedError
from domains.gateway.domain.quota_plan import (
    PROVIDER_NS,
    PlanQuotaSpec,
    QuotaPlanReservation,
    normalize_reset_strategy,
)
from domains.gateway.infrastructure.repositories.provider_plan_repository import (
    ProviderPlanRepository,
)
from libs.db.database import get_session_context
from utils.logging import get_logger

from domains.gateway.application.quota_plan_service import QuotaPlanService

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.provider_plan import (
        ProviderPlan,
        ProviderPlanQuota,
    )

logger = get_logger(__name__)


def _quota_to_spec(row: ProviderPlanQuota, *, plan: ProviderPlan) -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=row.id,
        label=row.label,
        window_seconds=row.window_seconds,
        limit_usd=row.limit_usd,
        limit_tokens=row.limit_tokens,
        limit_requests=row.limit_requests,
        reset_strategy=normalize_reset_strategy(row.reset_strategy),
        plan_valid_from=plan.valid_from,
    )


class ProviderPlanGuard:
    """轻量 facade：活跃套餐配置经 ``provider_plan_config_cache`` 缓存；loader 按需开 session。"""

    def __init__(self, *, quota_service: QuotaPlanService) -> None:
        self._quota = quota_service

    async def check_and_reserve(
        self,
        *,
        credential_id: uuid.UUID,
        real_model: str | None,
        estimate_tokens: int = 0,
        now: datetime | None = None,
    ) -> tuple[uuid.UUID | None, list[PlanQuotaSpec], list[QuotaPlanReservation]]:
        """命中活跃 plan 时返回 ``(plan_id, specs, reservations)``；未命中返回 ``(None, [], [])``。"""
        when = now or datetime.now(UTC)

        async def _loader() -> ProviderPlanConfigSnapshot | None:
            async with get_session_context() as session:
                repo = ProviderPlanRepository(session)
                plan = await repo.get_active_for_credential_model(
                    credential_id, real_model, now=when
                )
                if plan is None:
                    return None
                quotas = await repo.list_quotas(plan.id)
            return provider_plan_config_from_orm(plan, quotas)

        config = await get_cached_active_provider_plan(
            credential_id,
            real_model,
            now=when,
            loader=_loader,
        )
        if config is None:
            return None, [], []

        specs = plan_quota_specs_from_config(config)
        if not specs:
            return config.plan_id, [], []
        result = await self._quota.check_and_reserve(
            PROVIDER_NS,
            config.plan_id,
            specs,
            estimate_tokens=estimate_tokens,
            now=when,
        )
        if not result.allowed:
            exhausted = result.exhausted_snapshot
            label = exhausted.spec.label if exhausted is not None else "(unknown)"
            reason = (
                exhausted.exhausted_reason or "requests" if exhausted is not None else "requests"
            )
            cooldown_seconds = (
                exhausted.spec.window_seconds
                if exhausted is not None and exhausted.spec.window_seconds > 0
                else 60
            )
            raise ProviderPlanExhaustedError(
                plan_id=str(config.plan_id),
                quota_label=label,
                reason=reason,
                cooldown_seconds=cooldown_seconds,
            )
        return config.plan_id, specs, result.reservations

    async def commit(
        self,
        plan_id: uuid.UUID,
        specs: list[PlanQuotaSpec],
        *,
        delta_tokens: int,
        delta_usd: Decimal,
    ) -> None:
        if not specs:
            return
        await self._quota.commit(
            PROVIDER_NS,
            plan_id,
            specs,
            delta_tokens=delta_tokens,
            delta_usd=delta_usd,
        )

    async def release(
        self,
        plan_id: uuid.UUID,
        reservations: list[QuotaPlanReservation],
    ) -> None:
        if not reservations:
            return
        await self._quota.release(PROVIDER_NS, plan_id, reservations)

    async def mark_upstream_exhausted(
        self,
        plan_id: uuid.UUID,
        *,
        reason: str = "upstream_quota_exhausted",
        until: datetime | None = None,
    ) -> None:
        """收到上游 429/402/RESOURCE_EXHAUSTED 信号 → 立即把本地配额拉满。

        调用方传入命中的 plan_id（由 metadata 透传）。本方法独立解析 quotas，避免
        callbacks 持有 reservations 状态；失败仅记 warn 日志。
        """
        try:
            async with get_session_context() as session:
                repo = ProviderPlanRepository(session)
                plan = await repo.get(plan_id)
                if plan is None:
                    return
                quotas = await repo.list_quotas(plan_id)
            specs = [_quota_to_spec(q, plan=plan) for q in quotas]
            if not specs:
                return
            await self._quota.force_exhaust(
                PROVIDER_NS,
                plan_id,
                specs,
                until=until,
                reason=reason,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ProviderPlanGuard.mark_upstream_exhausted failed for plan %s: %s",
                plan_id,
                exc,
            )


# ---------------------------------------------------------------------------
# LiteLLM Router pre-call 集成
# ---------------------------------------------------------------------------

_provider_plan_guard_singleton: ProviderPlanGuard | None = None


def get_provider_plan_guard() -> ProviderPlanGuard:
    global _provider_plan_guard_singleton
    if _provider_plan_guard_singleton is None:
        from domains.gateway.application.quota_plan_service import (
            get_quota_plan_service,
        )

        _provider_plan_guard_singleton = ProviderPlanGuard(quota_service=get_quota_plan_service())
    return _provider_plan_guard_singleton


def _extract_credential_and_model(kwargs: dict[str, Any]) -> tuple[uuid.UUID | None, str | None]:
    """从 LiteLLM Router 调用 kwargs 中读出 deployment 的凭据与厂商模型字符串。"""
    cred_id: uuid.UUID | None = None
    real_model: str | None = None
    for container_key in ("litellm_params", "standard_logging_object"):
        container = kwargs.get(container_key)
        if not isinstance(container, dict):
            continue
        mi = container.get("model_info")
        if isinstance(mi, dict):
            raw_cid = mi.get("gateway_credential_id")
            if raw_cid:
                with suppress(ValueError, TypeError):
                    cred_id = uuid.UUID(str(raw_cid))
            raw_real = (
                mi.get("gateway_real_model")
                or mi.get("model_real")
                or container.get("model")
            )
            if isinstance(raw_real, str) and raw_real:
                real_model = raw_real
    if real_model is None:
        rm = kwargs.get("model")
        if isinstance(rm, str) and rm:
            real_model = rm
    return cred_id, real_model


def _metadata_dicts_on_call(data: dict[str, Any]) -> list[dict[str, Any]]:
    """pre_call ``data`` 上可能携带 metadata 的容器（与 proxy 出站一致）。"""
    out: list[dict[str, Any]] = []
    top = data.get("metadata")
    if isinstance(top, dict):
        out.append(top)
    litellm_params = data.get("litellm_params")
    if isinstance(litellm_params, dict):
        inner = litellm_params.get("metadata")
        if isinstance(inner, dict):
            out.append(inner)
    return out


def _stamp_provider_plan_on_call(
    data: dict[str, Any],
    *,
    plan_id: uuid.UUID,
    reservations: list[QuotaPlanReservation],
) -> None:
    """写入 plan_id / reservations，并镜像到 ``user_api_key_auth_metadata`` 供 callback 读取。"""
    plan_id_str = str(plan_id)
    reservations_payload = [
        {
            "quota_id": str(r.spec.quota_id),
            "minute_unix": r.minute_unix,
            "reserved_requests": r.reserved_requests,
        }
        for r in reservations
    ]
    gateway_fields: dict[str, Any] = {"gateway_provider_plan_id": plan_id_str}
    if reservations_payload:
        gateway_fields["gateway_provider_plan_reservations"] = reservations_payload

    for meta in _metadata_dicts_on_call(data):
        meta.update(gateway_fields)
        auth = meta.get("user_api_key_auth_metadata")
        if isinstance(auth, dict):
            auth.update(gateway_fields)
        else:
            meta["user_api_key_auth_metadata"] = dict(gateway_fields)


def build_provider_plan_pre_call_logger() -> Any:
    """构建 LiteLLM CustomLogger 实例，注册到 ``litellm.callbacks`` 实现 pre-call 配额校验。"""
    from litellm.integrations.custom_logger import CustomLogger  # type: ignore[import-not-found]

    guard = get_provider_plan_guard()

    class _Impl(CustomLogger):  # type: ignore[misc, valid-type]
        async def async_pre_call_hook(
            self,
            user_api_key_dict: Any,
            cache: Any,
            data: dict[str, Any],
            call_type: str,
        ) -> dict[str, Any] | None:
            # Phase2：成员+凭据+模型平台预算（部署已选）。耗尽抛 BudgetExceededError，
            # 直接 hard fail（HTTP 429），不进入 ProviderPlan / Router fallback。
            from domains.gateway.application.budget_deployment_check import (
                maybe_reserve_user_credential_budget,
            )

            await maybe_reserve_user_credential_budget(data)

            cred_id, real_model = _extract_credential_and_model(data)
            if cred_id is None:
                return None
            plan_id, _specs, reservations = await guard.check_and_reserve(
                credential_id=cred_id,
                real_model=real_model,
            )
            if plan_id is not None:
                _stamp_provider_plan_on_call(data, plan_id=plan_id, reservations=reservations)
            return None

    return _Impl()


__all__ = [
    "ProviderPlanGuard",
    "build_provider_plan_pre_call_logger",
    "get_provider_plan_guard",
]
