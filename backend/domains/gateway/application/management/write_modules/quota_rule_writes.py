"""配额规则批量写入（管理面写路径，按 layer 路由至各 aggregate）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal
import uuid

from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan
from domains.gateway.infrastructure.models.provider_plan import ProviderPlan
from libs.exceptions import AIAgentError, ValidationError
from utils.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal

    from domains.gateway.application.management.quota_rule_read_model import QuotaRuleReadModel


logger = get_logger(__name__)


QuotaRuleLayer = Literal["platform", "upstream", "downstream"]

QuotaRuleUpsertResult = GatewayBudget | ProviderPlan | EntitlementPlan


@dataclass(frozen=True)
class QuotaRuleUpsertCommand:
    layer: QuotaRuleLayer

    target_kind: str | None = None

    target_id: uuid.UUID | None = None

    user_id: uuid.UUID | None = None

    credential_id: uuid.UUID | None = None

    model_name: str | None = None

    period: str | None = None

    window_seconds: int | None = None

    reset_strategy: str | None = None

    quota_label: str | None = None

    access_kind: Literal["none", "vkey", "apikey_grant"] = "none"

    access_id: uuid.UUID | None = None

    included_models: list[str] | None = None

    limit_usd: Decimal | None = None

    soft_limit_usd: Decimal | None = None

    limit_tokens: int | None = None

    limit_requests: int | None = None

    unit_price_usd_per_token: Decimal | None = None

    unit_price_usd_per_request: Decimal | None = None

    plan_label: str | None = None

    valid_from: datetime | None = None

    valid_until: datetime | None = None


@dataclass(frozen=True)
class QuotaRuleBatchFailure:
    index: int

    error: str


@dataclass
class QuotaRuleBatchResult:
    succeeded: list[QuotaRuleReadModel]

    failed: list[QuotaRuleBatchFailure]


class QuotaRuleWritesMixin:
    """写侧 mixin — 由 GatewayManagementWriteService 组合。"""

    async def upsert_quota_rule(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> QuotaRuleUpsertResult:
        if cmd.layer == "platform":
            return await self._upsert_platform_quota_rule(
                cmd,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )

        if cmd.layer == "upstream":
            return await self._upsert_upstream_quota_rule(
                cmd,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )

        if cmd.layer == "downstream":
            return await self._upsert_downstream_quota_rule(
                cmd,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )

        raise ValidationError(f"不支持的配额层级: {cmd.layer}")

    async def batch_upsert_quota_rules(
        self,
        commands: list[QuotaRuleUpsertCommand],
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> QuotaRuleBatchResult:
        from domains.gateway.application.management.plan_read_mappers import (
            entitlement_plan_from_orm,
            provider_plan_from_orm,
        )
        from domains.gateway.application.management.quota_rule_read_mappers import (
            budget_to_quota_rule,
            flatten_entitlement_plan,
            flatten_provider_plan,
        )

        succeeded: list[QuotaRuleReadModel] = []

        failed: list[QuotaRuleBatchFailure] = []

        for index, cmd in enumerate(commands):
            try:
                result = await self.upsert_quota_rule(
                    cmd,
                    tenant_id=tenant_id,
                    is_platform_admin=is_platform_admin,
                )

                if cmd.layer == "platform":
                    succeeded.append(budget_to_quota_rule(result, team_id=tenant_id))

                elif cmd.layer == "upstream":
                    plan, quotas = await self._provider_plans.get_with_quotas(result.id)

                    if plan is not None:
                        model = provider_plan_from_orm(plan, quotas)

                        flat = flatten_provider_plan(model, team_id=tenant_id)

                        label = cmd.quota_label or "default"

                        matched = [r for r in flat if r.key.quota_label == label]

                        succeeded.extend(matched or flat[:1])

                else:
                    row = await self._entitlement_plans.get_with_quotas(result.id)

                    if row is not None:
                        plan, quotas = row

                        model = entitlement_plan_from_orm(plan, quotas)

                        flat = flatten_entitlement_plan(model, team_id=tenant_id)

                        label = cmd.quota_label or "default"

                        matched = [r for r in flat if r.key.quota_label == label]

                        succeeded.extend(matched or flat[:1])

            except (ValidationError, AIAgentError) as exc:
                logger.warning("quota rule batch upsert failed index=%s: %s", index, exc)

                failed.append(QuotaRuleBatchFailure(index=index, error=str(exc)))

        return QuotaRuleBatchResult(succeeded=succeeded, failed=failed)

    async def _upsert_platform_quota_rule(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> GatewayBudget:
        target_kind = cmd.target_kind

        if target_kind is None:
            if cmd.access_kind == "vkey" and cmd.access_id is not None:
                target_kind = "key"

            elif cmd.user_id is not None:
                target_kind = "user"

            else:
                target_kind = "tenant"

        target_id = cmd.target_id

        if target_kind == "tenant":
            target_id = tenant_id

        elif target_kind == "user":
            target_id = cmd.user_id or target_id

        elif target_kind == "key":
            target_id = cmd.access_id or target_id

        if target_kind == "key" and target_id is None:
            raise ValidationError("platform key 配额需要 access_id 或 target_id")

        if target_kind == "system" and not is_platform_admin:
            raise ValidationError("仅平台管理员可设置 system 配额")

        period = cmd.period or "monthly"

        await self._assert_budget_target_in_team(
            target_kind,
            target_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )

        return await self._budgets.upsert(
            target_kind=target_kind,
            target_id=target_id,
            period=period,
            model_name=cmd.model_name,
            limit_usd=cmd.limit_usd,
            soft_limit_usd=cmd.soft_limit_usd,
            limit_tokens=cmd.limit_tokens,
            limit_requests=cmd.limit_requests,
        )

    async def _upsert_upstream_quota_rule(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> ProviderPlan:
        if cmd.credential_id is None:
            raise ValidationError("upstream 配额需要 credential_id")

        await self._assert_credential_in_team(
            cmd.credential_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )

        label = cmd.quota_label or "default"

        window_seconds = cmd.window_seconds if cmd.window_seconds is not None else 0

        reset_strategy = cmd.reset_strategy or "rolling"

        real_model = cmd.model_name

        plan = await self._provider_plans.get_active_for_credential_model(
            cmd.credential_id,
            real_model,
        )

        if plan is None:
            now = datetime.now(UTC)

            plan = await self._provider_plans.create(
                credential_id=cmd.credential_id,
                real_model=real_model,
                label=cmd.plan_label or f"auto-{now.date().isoformat()}",
                valid_from=cmd.valid_from or now,
                valid_until=cmd.valid_until or (now + timedelta(days=365)),
            )

        existing_quotas = await self._provider_plans.list_quotas(plan.id)

        quota_payload = {
            "label": label,
            "window_seconds": window_seconds,
            "reset_strategy": reset_strategy,
            "limit_usd": cmd.limit_usd,
            "limit_tokens": cmd.limit_tokens,
            "limit_requests": cmd.limit_requests,
        }

        merged = [
            {
                "label": q.label,
                "window_seconds": q.window_seconds,
                "reset_strategy": q.reset_strategy,
                "limit_usd": q.limit_usd,
                "limit_tokens": q.limit_tokens,
                "limit_requests": q.limit_requests,
            }
            for q in existing_quotas
            if q.label != label
        ]

        merged.append(quota_payload)

        await self._provider_plans.replace_quotas(plan.id, merged)

        return plan

    async def _upsert_downstream_quota_rule(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> EntitlementPlan:
        if cmd.access_kind not in ("vkey", "apikey_grant") or cmd.access_id is None:
            raise ValidationError("downstream 配额需要 access_kind 与 access_id")

        scope = cmd.access_kind

        scope_id = cmd.access_id

        if scope == "vkey":
            await self._assert_vkey_in_team(
                scope_id,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )

        else:
            await self._assert_apikey_grant_in_team(
                scope_id,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )

        label = cmd.quota_label or "default"

        window_seconds = cmd.window_seconds if cmd.window_seconds is not None else 0

        reset_strategy = cmd.reset_strategy or "rolling"

        included_models: list[str] = list(cmd.included_models or [])

        if cmd.model_name and cmd.model_name not in included_models:
            included_models = [cmd.model_name]

        plan = await self._entitlement_plans.get_active_for_scope(
            scope,
            scope_id,
            virtual_model=cmd.model_name,
        )

        if plan is None:
            now = datetime.now(UTC)

            plan = await self._entitlement_plans.create(
                scope=scope,
                scope_id=scope_id,
                label=cmd.plan_label or f"auto-{now.date().isoformat()}",
                valid_from=cmd.valid_from or now,
                valid_until=cmd.valid_until or (now + timedelta(days=365)),
                included_models=included_models,
            )

            existing_quotas = []

        else:
            existing_quotas = await self._entitlement_plans.list_quotas(plan.id)

        quota_payload: dict[str, object] = {
            "label": label,
            "window_seconds": window_seconds,
            "reset_strategy": reset_strategy,
            "limit_usd": cmd.limit_usd,
            "limit_tokens": cmd.limit_tokens,
            "limit_requests": cmd.limit_requests,
        }

        if cmd.unit_price_usd_per_token is not None:
            quota_payload["unit_price_usd_per_token"] = cmd.unit_price_usd_per_token

        if cmd.unit_price_usd_per_request is not None:
            quota_payload["unit_price_usd_per_request"] = cmd.unit_price_usd_per_request

        merged = [
            {
                "label": q.label,
                "window_seconds": q.window_seconds,
                "reset_strategy": q.reset_strategy,
                "limit_usd": q.limit_usd,
                "limit_tokens": q.limit_tokens,
                "limit_requests": q.limit_requests,
                "unit_price_usd_per_token": getattr(q, "unit_price_usd_per_token", None),
                "unit_price_usd_per_request": getattr(q, "unit_price_usd_per_request", None),
            }
            for q in existing_quotas
            if q.label != label
        ]

        merged.append(quota_payload)

        await self._entitlement_plans.replace_quotas(plan.id, merged)

        return plan


__all__ = [
    "QuotaRuleBatchFailure",
    "QuotaRuleBatchResult",
    "QuotaRuleUpsertCommand",
    "QuotaRuleUpsertResult",
    "QuotaRuleWritesMixin",
]
