"""Gateway 管理面变更应用服务（写侧分包；对外 API 不变）。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.domain.errors import (
    ManagementEntityNotFoundError,
)
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan
from domains.gateway.infrastructure.models.provider_plan import ProviderPlan
from libs.exceptions import ValidationError
from utils.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal

    from domains.gateway.infrastructure.models.alert import GatewayAlertRule


logger = get_logger(__name__)



class EntitlementWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def upsert_budget(self, *, target_kind: str, target_id: uuid.UUID | None, period: str, model_name: str | None=None, limit_usd: Decimal | None, soft_limit_usd: Decimal | None=None, limit_tokens: int | None, limit_requests: int | None) -> Any:
        return await self._budgets.upsert(target_kind=target_kind, target_id=target_id, period=period, model_name=model_name, limit_usd=limit_usd, soft_limit_usd=soft_limit_usd, limit_tokens=limit_tokens, limit_requests=limit_requests)

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

    async def create_alert_rule(self, *, tenant_id: uuid.UUID, name: str, description: str | None, metric: str, threshold: Decimal, window_minutes: int, channels: dict[str, Any], enabled: bool) -> GatewayAlertRule:
        return await self._alerts.create_rule(tenant_id=tenant_id, name=name, description=description, metric=metric, threshold=threshold, window_minutes=window_minutes, channels=channels, enabled=enabled)

    async def update_alert_rule(self, rule_id: uuid.UUID, *, tenant_id: uuid.UUID, fields: dict[str, Any]) -> GatewayAlertRule:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.tenant_id != tenant_id:
            raise ManagementEntityNotFoundError('alert_rule', str(rule_id))
        return await self._alerts.update_rule_fields(rule, fields)

    async def delete_alert_rule(self, rule_id: uuid.UUID, *, tenant_id: uuid.UUID) -> None:
        rule = await self._alerts.get_rule(rule_id)
        if rule is None or rule.tenant_id != tenant_id:
            raise ManagementEntityNotFoundError('alert_rule', str(rule_id))
        await self._alerts.delete_rule(rule)

    async def create_provider_plan(self, *, credential_id: uuid.UUID, tenant_id: uuid.UUID, is_platform_admin: bool, real_model: str | None, label: str, valid_from: datetime, valid_until: datetime, is_active: bool=True, auto_renew: bool=False, notes: str | None=None, extra: dict[str, Any] | None=None, quotas: list[dict[str, Any]] | None=None) -> ProviderPlan:
        await self._assert_credential_in_team(credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        plan = await self._provider_plans.create(credential_id=credential_id, real_model=real_model, label=label, valid_from=valid_from, valid_until=valid_until, is_active=is_active, auto_renew=auto_renew, notes=notes, extra=extra)
        for q in quotas or []:
            await self._provider_plans.add_quota(plan_id=plan.id, **q)
        return plan

    async def update_provider_plan(self, plan_id: uuid.UUID, *, credential_id: uuid.UUID, tenant_id: uuid.UUID, is_platform_admin: bool, fields: dict[str, Any], quotas: list[dict[str, Any]] | None=None) -> ProviderPlan:
        await self._assert_credential_in_team(credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        await self._assert_provider_plan_in_credential(plan_id, credential_id=credential_id)
        await self._provider_plans.update(plan_id, **fields)
        if quotas is not None:
            await self._provider_plans.replace_quotas(plan_id, quotas)
        result = await self._provider_plans.get(plan_id)
        if result is None:
            raise ManagementEntityNotFoundError('provider_plan', str(plan_id))
        return result

    async def delete_provider_plan(self, plan_id: uuid.UUID, *, credential_id: uuid.UUID, tenant_id: uuid.UUID, is_platform_admin: bool) -> None:
        await self._assert_credential_in_team(credential_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        await self._assert_provider_plan_in_credential(plan_id, credential_id=credential_id)
        ok = await self._provider_plans.delete(plan_id)
        if not ok:
            raise ManagementEntityNotFoundError('provider_plan', str(plan_id))

    async def create_entitlement_plan(self, *, scope: str, scope_id: uuid.UUID, tenant_id: uuid.UUID, is_platform_admin: bool, label: str, valid_from: datetime, valid_until: datetime, included_models: list[str] | None=None, included_capabilities: list[str] | None=None, is_active: bool=True, auto_renew: bool=False, notes: str | None=None, extra: dict[str, Any] | None=None, quotas: list[dict[str, Any]] | None=None) -> EntitlementPlan:
        if scope == 'vkey':
            await self._assert_vkey_in_team(scope_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        elif scope == 'apikey_grant':
            await self._assert_apikey_grant_in_team(scope_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        else:
            raise ValidationError(f'不支持的 entitlement scope: {scope}')
        plan = await self._entitlement_plans.create(scope=scope, scope_id=scope_id, label=label, valid_from=valid_from, valid_until=valid_until, included_models=included_models, included_capabilities=included_capabilities, is_active=is_active, auto_renew=auto_renew, notes=notes, extra=extra)
        for q in quotas or []:
            await self._entitlement_plans.add_quota(plan_id=plan.id, **q)
        return plan

    async def update_entitlement_plan(self, plan_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool, fields: dict[str, Any], quotas: list[dict[str, Any]] | None=None) -> EntitlementPlan:
        await self._assert_entitlement_plan_in_team(plan_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        await self._entitlement_plans.update(plan_id, **fields)
        if quotas is not None:
            await self._entitlement_plans.replace_quotas(plan_id, quotas)
        result = await self._entitlement_plans.get(plan_id)
        if result is None:
            raise ManagementEntityNotFoundError('entitlement_plan', str(plan_id))
        return result

    async def delete_entitlement_plan(self, plan_id: uuid.UUID, *, tenant_id: uuid.UUID, is_platform_admin: bool) -> None:
        await self._assert_entitlement_plan_in_team(plan_id, tenant_id=tenant_id, is_platform_admin=is_platform_admin)
        ok = await self._entitlement_plans.delete(plan_id)
        if not ok:
            raise ManagementEntityNotFoundError('entitlement_plan', str(plan_id))
