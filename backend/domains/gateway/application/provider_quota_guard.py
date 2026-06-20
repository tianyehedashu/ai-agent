"""ProviderQuotaGuard - 上游扁平配额 pre-call 校验"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
import uuid

from domains.gateway.application.provider_quota_config_cache import (
    ProviderQuotaConfigRow,
    enforceable_specs_from_rows,
    get_cached_provider_quotas,
    provider_quota_rows_from_orm,
    quota_row_to_spec,
)
from domains.gateway.application.quota_plan_callback_settlement_shared import to_plan_uuid
from domains.gateway.application.quota_plan_service import QuotaPlanService
from domains.gateway.domain.deployment_cooldown_port import DeploymentCooldownPort
from domains.gateway.domain.errors import ProviderPlanExhaustedError
from domains.gateway.domain.litellm_deployment_attribution import (
    gateway_deployment_credential_id,
    gateway_deployment_id,
    gateway_deployment_real_model,
)
from domains.gateway.domain.quota_plan import PROVIDER_NS, PlanQuotaSpec, QuotaPlanReservation
from domains.gateway.infrastructure.repositories.provider_quota_repository import (
    ProviderQuotaRepository,
)
from libs.db.database import get_session_context
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ProviderQuotaReservation:
    """单条扁平规则的预扣结果（plan_id = quota_id = rule_id）。"""

    rule_id: uuid.UUID
    spec: PlanQuotaSpec
    reservation: QuotaPlanReservation


class ProviderQuotaGuard:
    def __init__(
        self,
        *,
        quota_service: QuotaPlanService,
        cooldown: DeploymentCooldownPort | None = None,
    ) -> None:
        self._quota = quota_service
        self._cooldown = cooldown

    async def check_and_reserve(
        self,
        *,
        credential_id: uuid.UUID,
        real_model: str | None,
        estimate_tokens: int = 0,
        now: datetime | None = None,
        deployment_id: str | None = None,
    ) -> list[ProviderQuotaReservation]:
        when = now or datetime.now(UTC)

        async def _loader() -> tuple[ProviderQuotaConfigRow, ...]:
            async with get_session_context() as session:
                repo = ProviderQuotaRepository(session)
                rules = await repo.list_active_for_credential_model(
                    credential_id, real_model, now=when
                )
            return provider_quota_rows_from_orm(rules)

        rows = await get_cached_provider_quotas(
            credential_id,
            real_model,
            loader=_loader,
        )
        specs = enforceable_specs_from_rows(rows, now=when)
        if not specs:
            return []

        reserved: list[ProviderQuotaReservation] = []
        try:
            for spec in specs:
                result = await self._quota.check_and_reserve(
                    PROVIDER_NS,
                    spec.quota_id,
                    [spec],
                    estimate_tokens=estimate_tokens,
                    now=when,
                )
                if not result.allowed:
                    exhausted = result.exhausted_snapshot
                    label = exhausted.spec.label if exhausted is not None else spec.label
                    reason = (
                        exhausted.exhausted_reason or "requests"
                        if exhausted is not None
                        else "requests"
                    )
                    cooldown_seconds = (
                        exhausted.spec.window_seconds
                        if exhausted is not None and exhausted.spec.window_seconds > 0
                        else 60
                    )
                    raise ProviderPlanExhaustedError(
                        plan_id=str(spec.quota_id),
                        quota_label=label,
                        reason=reason,
                        cooldown_seconds=cooldown_seconds,
                    )
                if result.reservations:
                    reserved.append(
                        ProviderQuotaReservation(
                            rule_id=spec.quota_id,
                            spec=spec,
                            reservation=result.reservations[0],
                        )
                    )
        except ProviderPlanExhaustedError as exc:
            await self._release_all(reserved)
            await self._maybe_cooldown_deployment(deployment_id, exc)
            raise
        return reserved

    async def _maybe_cooldown_deployment(
        self,
        deployment_id: str | None,
        exc: ProviderPlanExhaustedError,
    ) -> None:
        """配额耗尽时把当前 deployment 加入 Router cooldown，避免反复选中。"""
        if self._cooldown is None or not deployment_id:
            return
        await self._cooldown.cooldown_deployment(
            deployment_id=deployment_id,
            reason=f"provider_quota_exhausted:{exc.reason}",
        )

    async def _release_all(self, reserved: list[ProviderQuotaReservation]) -> None:
        for item in reserved:
            await self._quota.release(
                PROVIDER_NS,
                item.rule_id,
                [item.reservation],
            )

    async def commit_rule(
        self,
        rule_id: uuid.UUID,
        spec: PlanQuotaSpec,
        *,
        delta_tokens: int,
        delta_usd: Decimal,
    ) -> None:
        await self._quota.commit(
            PROVIDER_NS,
            rule_id,
            [spec],
            delta_tokens=delta_tokens,
            delta_usd=delta_usd,
        )

    async def release_rule(self, item: ProviderQuotaReservation) -> None:
        await self._quota.release(PROVIDER_NS, item.rule_id, [item.reservation])

    async def mark_upstream_exhausted(
        self,
        rule_id: uuid.UUID,
        *,
        reason: str = "upstream_quota_exhausted",
        until: datetime | None = None,
    ) -> None:
        await self.mark_upstream_exhausted_rules([rule_id], reason=reason, until=until)

    async def mark_upstream_exhausted_rules(
        self,
        rule_ids: list[uuid.UUID],
        *,
        reason: str = "upstream_quota_exhausted",
        until: datetime | None = None,
    ) -> None:
        unique_ids = list(dict.fromkeys(rule_ids))
        for rule_id in unique_ids:
            await self._mark_single_upstream_exhausted(
                rule_id, reason=reason, until=until
            )

    async def _mark_single_upstream_exhausted(
        self,
        rule_id: uuid.UUID,
        *,
        reason: str,
        until: datetime | None,
    ) -> None:
        try:
            async with get_session_context() as session:
                repo = ProviderQuotaRepository(session)
                row = await repo.get(rule_id)
            if row is None:
                return
            spec = quota_row_to_spec(
                ProviderQuotaConfigRow(
                    rule_id=row.id,
                    label=row.label,
                    window_seconds=row.window_seconds,
                    reset_strategy=row.reset_strategy,
                    reset_timezone=row.reset_timezone,
                    reset_time_minutes=row.reset_time_minutes,
                    reset_day_of_month=row.reset_day_of_month,
                    limit_usd=row.limit_usd,
                    limit_tokens=row.limit_tokens,
                    limit_requests=row.limit_requests,
                    enabled=row.enabled,
                    valid_from=row.valid_from,
                    valid_until=row.valid_until,
                )
            )
            await self._quota.force_exhaust(
                PROVIDER_NS,
                rule_id,
                [spec],
                until=until,
                reason=reason,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "ProviderQuotaGuard.mark_upstream_exhausted failed for rule %s: %s",
                rule_id,
                exc,
            )


_provider_quota_guard_singleton: ProviderQuotaGuard | None = None


def get_provider_quota_guard() -> ProviderQuotaGuard:
    global _provider_quota_guard_singleton
    if _provider_quota_guard_singleton is None:
        from domains.gateway.application.quota_plan_service import get_quota_plan_service
        from domains.gateway.infrastructure.litellm_router_deployment_cooldown_adapter import (
            LiteLLMRouterDeploymentCooldownAdapter,
        )

        _provider_quota_guard_singleton = ProviderQuotaGuard(
            quota_service=get_quota_plan_service(),
            cooldown=LiteLLMRouterDeploymentCooldownAdapter(),
        )
    return _provider_quota_guard_singleton


def _extract_credential_and_model(data: dict[str, Any]) -> tuple[uuid.UUID | None, str | None]:
    return gateway_deployment_credential_id(data), gateway_deployment_real_model(data)


def _metadata_dicts_on_call(data: dict[str, Any]) -> list[dict[str, Any]]:
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


def _stamp_provider_quotas_on_call(
    data: dict[str, Any],
    *,
    reserved: list[ProviderQuotaReservation],
) -> None:
    if not reserved:
        return
    primary_rule_id = str(reserved[0].rule_id)
    reservations_payload = [
        {
            "rule_id": str(item.rule_id),
            "quota_id": str(item.spec.quota_id),
            "minute_unix": item.reservation.minute_unix,
            "reserved_requests": item.reservation.reserved_requests,
        }
        for item in reserved
    ]
    gateway_fields: dict[str, Any] = {
        # 主命中规则 id；同时落 gateway_request_logs.provider_plan_id 列（拍平后即 quota_id）。
        "gateway_provider_plan_id": primary_rule_id,
        "gateway_provider_quota_reservations": reservations_payload,
    }

    for meta in _metadata_dicts_on_call(data):
        meta.update(gateway_fields)
        auth = meta.get("user_api_key_auth_metadata")
        if isinstance(auth, dict):
            auth.update(gateway_fields)
        else:
            meta["user_api_key_auth_metadata"] = dict(gateway_fields)


def upstream_rule_ids_from_call_data(data: dict[str, Any]) -> list[uuid.UUID]:
    """从 pre_call / callback metadata 收集本次命中的全部上游扁平 rule_id。"""
    ids: list[uuid.UUID] = []
    for meta in _metadata_dicts_on_call(data):
        raw = meta.get("gateway_provider_quota_reservations")
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                rid = to_plan_uuid(item.get("rule_id")) or to_plan_uuid(item.get("quota_id"))
                if rid is not None and rid not in ids:
                    ids.append(rid)
        primary = to_plan_uuid(meta.get("gateway_provider_plan_id"))
        if primary is not None and primary not in ids:
            ids.append(primary)
    return ids


async def _apply_provider_quota_pre_call(data: dict[str, Any]) -> None:
    from domains.gateway.application.budget_deployment_check import (
        maybe_reserve_user_credential_budget,
    )

    await maybe_reserve_user_credential_budget(data)

    guard = get_provider_quota_guard()
    cred_id, real_model = _extract_credential_and_model(data)
    if cred_id is None:
        return
    reserved = await guard.check_and_reserve(
        credential_id=cred_id,
        real_model=real_model,
        deployment_id=gateway_deployment_id(data),
    )
    if reserved:
        _stamp_provider_quotas_on_call(data, reserved=reserved)


def build_provider_quota_pre_call_logger() -> Any:
    from litellm.integrations.custom_logger import CustomLogger  # type: ignore[import-not-found]

    class _Impl(CustomLogger):  # type: ignore[misc, valid-type]
        async def async_pre_call_hook(
            self,
            user_api_key_dict: Any,
            cache: Any,
            data: dict[str, Any],
            call_type: str,
        ) -> dict[str, Any] | None:
            await _apply_provider_quota_pre_call(data)
            return None

        async def async_pre_call_deployment_hook(
            self,
            kwargs: dict[str, Any],
            call_type: Any,
        ) -> dict[str, Any] | None:
            await _apply_provider_quota_pre_call(kwargs)
            return kwargs

    return _Impl()


__all__ = [
    "ProviderQuotaGuard",
    "ProviderQuotaReservation",
    "build_provider_quota_pre_call_logger",
    "get_provider_quota_guard",
    "upstream_rule_ids_from_call_data",
]
