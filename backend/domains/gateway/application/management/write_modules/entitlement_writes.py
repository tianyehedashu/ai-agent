"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.domain.errors import (
    ManagementEntityNotFoundError,
)
from domains.gateway.domain.policies.plan_quota_reset_anchor_policy import (
    resolve_plan_quota_reset_anchor,
)
from domains.gateway.domain.policies.platform_budget_upsert_policy import (
    validate_platform_budget_upsert,
)
from domains.gateway.domain.quota_plan import default_reset_strategy_for_window
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan
from domains.gateway.infrastructure.models.provider_plan import ProviderPlan
from libs.exceptions import ValidationError
from utils.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal

    from domains.gateway.infrastructure.models.alert import GatewayAlertRule


logger = get_logger(__name__)


def _normalize_plan_quota_items(quotas: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for quota in quotas or []:
        window_seconds = int(quota.get("window_seconds") or 0)
        # 未显式指定策略时按窗口长度自动推导（与 quota_rule_writes 同一真源），
        # 避免日/月窗口被静默落成 rolling。
        reset_strategy = str(
            quota.get("reset_strategy") or default_reset_strategy_for_window(window_seconds)
        )
        reset_time_raw = quota.get("reset_time_minutes")
        reset_day_raw = quota.get("reset_day_of_month")
        anchor = resolve_plan_quota_reset_anchor(
            window_seconds=window_seconds,
            reset_strategy=reset_strategy,
            reset_timezone=(
                str(quota["reset_timezone"])
                if quota.get("reset_timezone") is not None
                else None
            ),
            reset_time_minutes=int(reset_time_raw) if reset_time_raw is not None else None,
            reset_day_of_month=int(reset_day_raw) if reset_day_raw is not None else None,
        )
        out.append(
            {
                **quota,
                "reset_strategy": reset_strategy,
                "reset_timezone": anchor.timezone,
                "reset_time_minutes": anchor.time_minutes,
                "reset_day_of_month": anchor.day_of_month,
            }
        )
    return out


class EntitlementWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def upsert_budget(
        self,
        *,
        target_kind: str,
        target_id: uuid.UUID | None,
        period: str,
        model_name: str | None = None,
        limit_usd: Decimal | None,
        soft_limit_usd: Decimal | None = None,
        limit_tokens: int | None,
        limit_requests: int | None,
        period_timezone: str | None = None,
        period_reset_minutes: int | None = None,
        period_reset_day: int | None = None,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> Any:
        _ = soft_limit_usd
        await self._assert_budget_target_in_team(
            target_kind,
            target_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )
        anchor = validate_platform_budget_upsert(
            target_kind=target_kind,
            credential_id=None,
            model_name=model_name,
            period=period,
            limit_usd=limit_usd,
            limit_tokens=limit_tokens,
            limit_requests=limit_requests,
            period_timezone=period_timezone,
            period_reset_minutes=period_reset_minutes,
            period_reset_day=period_reset_day,
        )
        # 成员总量/模型护栏按团队隔离（user 维度，无凭据）。
        budget_tenant = tenant_id if target_kind == "user" else None
        budget = await self._budgets.upsert(
            target_kind=target_kind,
            target_id=target_id,
            period=period,
            model_name=model_name,
            tenant_id=budget_tenant,
            limit_usd=limit_usd,
            soft_limit_usd=None,
            limit_tokens=limit_tokens,
            limit_requests=limit_requests,
            period_timezone=anchor.timezone,
            period_reset_minutes=anchor.time_minutes,
            period_reset_day=anchor.day_of_month,
        )
        from domains.gateway.application.gateway_cache_invalidation import (
            invalidate_gateway_budget_config_cache,
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_budget_config_cache()
        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)
        self.invalidate_tenant_gateway_read_caches(tenant_id)
        return budget

    async def delete_budget(
        self,
        budget_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> None:
        await self._assert_budget_in_team(
            budget_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )
        deleted = await self._budgets.delete(budget_id)
        if not deleted:
            raise ManagementEntityNotFoundError("budget", str(budget_id))
        from domains.gateway.application.gateway_cache_invalidation import (
            invalidate_gateway_budget_config_cache,
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_budget_config_cache()
        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)
        self.invalidate_tenant_gateway_read_caches(tenant_id)

    async def delete_self_budget(
        self,
        budget_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> None:
        """成员自助删除：仅允许删本人「user + 本人凭据」的 platform 配额行。"""
        budget = await self._budgets.get(budget_id)
        if budget is None:
            raise ManagementEntityNotFoundError("budget", str(budget_id))
        if (
            budget.target_kind != "user"
            or budget.target_id != actor_user_id
            or budget.credential_id is None
        ):
            raise ManagementEntityNotFoundError("budget", str(budget_id))
        await self._assert_credential_owned_by_actor(
            budget.credential_id,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
        )
        deleted = await self._budgets.delete(budget_id)
        if not deleted:
            raise ManagementEntityNotFoundError("budget", str(budget_id))
        from domains.gateway.application.gateway_cache_invalidation import (
            invalidate_gateway_budget_config_cache,
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_budget_config_cache()
        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)
        self.invalidate_tenant_gateway_read_caches(tenant_id)

    async def create_alert_rule(
        self,
        *,
        tenant_id: uuid.UUID,
        name: str,
        description: str | None,
        metric: str,
        threshold: Decimal,
        window_minutes: int,
        channels: dict[str, Any],
        enabled: bool,
    ) -> GatewayAlertRule:
        return await self._alerts.create_rule(
            tenant_id=tenant_id,
            name=name,
            description=description,
            metric=metric,
            threshold=threshold,
            window_minutes=window_minutes,
            channels=channels,
            enabled=enabled,
        )

    async def update_alert_rule(
        self, rule_id: uuid.UUID, *, tenant_id: uuid.UUID, fields: dict[str, Any]
    ) -> GatewayAlertRule:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.tenant_id != tenant_id:
            raise ManagementEntityNotFoundError("alert_rule", str(rule_id))
        return await self._alerts.update_rule_fields(rule, fields)

    async def delete_alert_rule(self, rule_id: uuid.UUID, *, tenant_id: uuid.UUID) -> None:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.tenant_id != tenant_id:
            raise ManagementEntityNotFoundError("alert_rule", str(rule_id))
        await self._alerts.delete_rule(rule)

    async def create_provider_plan(
        self,
        *,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        actor_user_id: uuid.UUID | None = None,
        real_model: str | None,
        label: str,
        valid_from: datetime,
        valid_until: datetime,
        is_active: bool = True,
        auto_renew: bool = False,
        notes: str | None = None,
        extra: dict[str, Any] | None = None,
        quotas: list[dict[str, Any]] | None = None,
    ) -> ProviderPlan:
        await self._assert_credential_in_team(
            credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
        )
        if real_model:
            real_model = await self._resolve_registered_real_model(credential_id, real_model)
        plan = await self._provider_plans.create(
            credential_id=credential_id,
            real_model=real_model,
            label=label,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=is_active,
            auto_renew=auto_renew,
            notes=notes,
            extra=extra,
        )
        for q in _normalize_plan_quota_items(quotas):
            await self._provider_plans.add_quota(plan_id=plan.id, **q)
        await self._invalidate_upstream_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
        )
        return plan

    async def update_provider_plan(
        self,
        plan_id: uuid.UUID,
        *,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        actor_user_id: uuid.UUID | None = None,
        fields: dict[str, Any],
        quotas: list[dict[str, Any]] | None = None,
    ) -> ProviderPlan:
        await self._assert_credential_in_team(
            credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
        )
        await self._assert_provider_plan_in_credential(plan_id, credential_id=credential_id)
        next_real_model = fields.get("real_model")
        if isinstance(next_real_model, str) and next_real_model:
            fields = {
                **fields,
                "real_model": await self._resolve_registered_real_model(
                    credential_id, next_real_model
                ),
            }
        await self._provider_plans.update(plan_id, **fields)
        if quotas is not None:
            await self._provider_plans.replace_quotas(
                plan_id,
                _normalize_plan_quota_items(quotas),
            )
        result = await self._provider_plans.get(plan_id)
        if result is None:
            raise ManagementEntityNotFoundError("provider_plan", str(plan_id))
        await self._invalidate_upstream_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
        )
        return result

    async def delete_provider_plan(
        self,
        plan_id: uuid.UUID,
        *,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        actor_user_id: uuid.UUID | None = None,
    ) -> None:
        await self._assert_credential_in_team(
            credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
        )
        await self._assert_provider_plan_in_credential(plan_id, credential_id=credential_id)
        ok = await self._provider_plans.delete(plan_id)
        if not ok:
            raise ManagementEntityNotFoundError("provider_plan", str(plan_id))
        await self._invalidate_upstream_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
        )

    async def create_entitlement_plan(
        self,
        *,
        scope: str,
        scope_id: uuid.UUID,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        label: str,
        valid_from: datetime,
        valid_until: datetime,
        included_models: list[str] | None = None,
        included_capabilities: list[str] | None = None,
        is_active: bool = True,
        auto_renew: bool = False,
        notes: str | None = None,
        extra: dict[str, Any] | None = None,
        quotas: list[dict[str, Any]] | None = None,
    ) -> EntitlementPlan:
        if scope == "vkey":
            await self._assert_vkey_in_team(
                scope_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        elif scope == "apikey_grant":
            await self._assert_apikey_grant_in_team(
                scope_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
            )
        else:
            raise ValidationError(f"不支持的 entitlement scope: {scope}")
        plan = await self._entitlement_plans.create(
            scope=scope,
            scope_id=scope_id,
            label=label,
            valid_from=valid_from,
            valid_until=valid_until,
            included_models=included_models,
            included_capabilities=included_capabilities,
            is_active=is_active,
            auto_renew=auto_renew,
            notes=notes,
            extra=extra,
        )
        for q in _normalize_plan_quota_items(quotas):
            await self._entitlement_plans.add_quota(plan_id=plan.id, **q)
        from domains.gateway.application.gateway_cache_invalidation import (
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)
        return plan

    async def update_entitlement_plan(
        self,
        plan_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        fields: dict[str, Any],
        quotas: list[dict[str, Any]] | None = None,
    ) -> EntitlementPlan:
        await self._assert_entitlement_plan_in_team(
            plan_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
        )
        await self._entitlement_plans.update(plan_id, **fields)
        if quotas is not None:
            await self._entitlement_plans.replace_quotas(
                plan_id,
                _normalize_plan_quota_items(quotas),
            )
        result = await self._entitlement_plans.get(plan_id)
        if result is None:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        from domains.gateway.application.gateway_cache_invalidation import (
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)
        return result

    async def delete_entitlement_plan(
        self, plan_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool
    ) -> None:
        await self._assert_entitlement_plan_in_team(
            plan_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin
        )
        ok = await self._entitlement_plans.delete(plan_id)
        if not ok:
            raise ManagementEntityNotFoundError("entitlement_plan", str(plan_id))
        from domains.gateway.application.gateway_cache_invalidation import (
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)
