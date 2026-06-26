"""配额规则批量写入（管理面写路径，按 layer 路由至各 aggregate）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal
import uuid

from domains.gateway.domain.period_reset_anchor import PeriodResetAnchor
from domains.gateway.domain.policies.plan_quota_reset_anchor_policy import (
    resolve_plan_quota_reset_anchor,
)
from domains.gateway.domain.policies.platform_budget_upsert_policy import (
    validate_platform_budget_upsert,
)
from domains.gateway.domain.quota_plan import default_reset_strategy_for_window
from domains.gateway.infrastructure.models.budget import GatewayBudget
from domains.gateway.infrastructure.models.entitlement_plan import EntitlementPlan
from domains.gateway.infrastructure.models.provider_quota import ProviderQuota
from libs.exceptions import AIAgentError, ValidationError
from utils.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal

    from domains.gateway.application.management.quota_rule_read_model import QuotaRuleReadModel


logger = get_logger(__name__)


def _plan_reset_fields_from_cmd(
    cmd: QuotaRuleUpsertCommand,
    *,
    window_seconds: int,
    reset_strategy: str,
) -> dict[str, object]:
    anchor = resolve_plan_quota_reset_anchor(
        window_seconds=window_seconds,
        reset_strategy=reset_strategy,
        reset_timezone=cmd.reset_timezone or cmd.period_timezone,
        reset_time_minutes=cmd.reset_time_minutes
        if cmd.reset_time_minutes is not None
        else cmd.period_reset_minutes,
        reset_day_of_month=cmd.reset_day_of_month
        if cmd.reset_day_of_month is not None
        else cmd.period_reset_day,
    )
    return {
        "reset_timezone": anchor.timezone,
        "reset_time_minutes": anchor.time_minutes,
        "reset_day_of_month": anchor.day_of_month,
    }


QuotaRuleLayer = Literal["platform", "upstream", "downstream"]

QuotaRuleUpsertResult = GatewayBudget | ProviderQuota | EntitlementPlan


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

    limit_images: int | None = None

    unit_price_usd_per_token: Decimal | None = None

    unit_price_usd_per_request: Decimal | None = None

    plan_label: str | None = None

    valid_from: datetime | None = None

    valid_until: datetime | None = None

    enabled: bool = True

    period_timezone: str | None = None
    period_reset_minutes: int | None = None
    period_reset_day: int | None = None
    reset_timezone: str | None = None
    reset_time_minutes: int | None = None
    reset_day_of_month: int | None = None


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
        actor_user_id: uuid.UUID | None = None,
    ) -> QuotaRuleUpsertResult:
        if cmd.layer == "platform":
            return await self._upsert_platform_quota_rule(
                cmd,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )

        if cmd.layer == "upstream":
            if actor_user_id is None:
                raise ValidationError("upstream 配额写入需要 actor_user_id")
            quota, _display_team_id = await self._upsert_upstream_quota_rule(
                cmd,
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                is_platform_admin=is_platform_admin,
            )
            return quota

        if cmd.layer == "downstream":
            return await self._upsert_downstream_quota_rule(
                cmd,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )

        raise ValidationError(f"不支持的配额层级: {cmd.layer}")

    async def batch_upsert_self_quota_rules(
        self,
        commands: list[QuotaRuleUpsertCommand],
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> QuotaRuleBatchResult:
        """成员自助：仅允许写「本人 user + 本人凭据(+模型)」的 platform 配额。

        通过 ``member_self_service=True`` 触发自助校验（强制 target_kind=user /
        target_id=actor / 凭据归属本人）；非 platform 命令直接失败。
        """
        return await self.batch_upsert_quota_rules(
            commands,
            tenant_id=tenant_id,
            is_platform_admin=False,
            actor_user_id=actor_user_id,
            member_self_service=True,
        )

    async def batch_upsert_quota_rules(
        self,
        commands: list[QuotaRuleUpsertCommand],
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        actor_user_id: uuid.UUID | None = None,
        member_self_service: bool = False,
    ) -> QuotaRuleBatchResult:
        from domains.gateway.application.management.plan_read_mappers import (
            entitlement_plan_from_orm,
            provider_quota_from_orm,
        )
        from domains.gateway.application.management.quota_rule_read_mappers import (
            budget_to_quota_rule,
            flatten_entitlement_plan,
            provider_quota_to_quota_rule,
        )

        succeeded: list[QuotaRuleReadModel] = []
        failed: list[QuotaRuleBatchFailure] = []
        any_changed = False
        upstream_changed = False

        platform_items: list[tuple[int, dict[str, object]]] = []
        non_platform_commands: list[tuple[int, QuotaRuleUpsertCommand]] = []

        for index, cmd in enumerate(commands):
            if cmd.layer == "platform":
                try:
                    item = await self._prepare_platform_upsert_item(
                        cmd,
                        tenant_id=tenant_id,
                        is_platform_admin=is_platform_admin,
                        actor_user_id=actor_user_id,
                        member_self_service=member_self_service,
                    )
                    platform_items.append((index, item))
                except (ValidationError, AIAgentError) as exc:
                    logger.warning("quota rule batch upsert failed index=%s: %s", index, exc)
                    failed.append(QuotaRuleBatchFailure(index=index, error=str(exc)))
            elif member_self_service and cmd.layer != "upstream":
                failed.append(
                    QuotaRuleBatchFailure(
                        index=index,
                        error="成员自助配额仅支持平台 与本人凭据的 upstream 层",
                    )
                )
            else:
                non_platform_commands.append((index, cmd))

        if platform_items:
            batch_results = await self._budgets.batch_upsert([item for _, item in platform_items])
            for (_, _), budget in zip(platform_items, batch_results, strict=True):
                await self._maybe_index_user_credential_budget(budget)
                succeeded.append(budget_to_quota_rule(budget, team_id=tenant_id))
                any_changed = True
            from domains.gateway.application.gateway_cache_invalidation import (
                invalidate_gateway_budget_config_cache,
            )

            await invalidate_gateway_budget_config_cache()

        for index, cmd in non_platform_commands:
            try:
                if actor_user_id is None:
                    raise ValidationError("upstream/downstream 配额写入需要 actor_user_id")
                display_team_id = tenant_id
                if cmd.layer == "upstream":
                    result, display_team_id = await self._upsert_upstream_quota_rule(
                        cmd,
                        tenant_id=tenant_id,
                        actor_user_id=actor_user_id,
                        is_platform_admin=is_platform_admin,
                    )
                else:
                    result = await self.upsert_quota_rule(
                        cmd,
                        tenant_id=tenant_id,
                        is_platform_admin=is_platform_admin,
                        actor_user_id=actor_user_id,
                    )
                any_changed = True
                if cmd.layer == "upstream":
                    upstream_changed = True
                    read_model = provider_quota_from_orm(result)
                    rule = provider_quota_to_quota_rule(read_model, team_id=display_team_id)
                    label = cmd.quota_label or "default"
                    if rule.key.quota_label == label:
                        succeeded.append(rule)
                    else:
                        succeeded.append(rule)
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

        if any_changed:
            await self._invalidate_quota_rule_list_cache(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                upstream_changed=upstream_changed,
            )

        return QuotaRuleBatchResult(succeeded=succeeded, failed=failed)

    async def _resolve_platform_target(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        actor_user_id: uuid.UUID | None = None,
        member_self_service: bool = False,
    ) -> tuple[str, uuid.UUID | None, uuid.UUID | None, str, PeriodResetAnchor]:
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

        if member_self_service:
            if actor_user_id is None:
                raise ValidationError("成员自助配额需要 actor_user_id")
            if target_kind != "user":
                raise ValidationError("成员自助配额仅支持设置本人维度（target_kind=user）")
            if target_id != actor_user_id:
                raise ValidationError("成员自助配额只能设置本人额度")
            if cmd.credential_id is None:
                raise ValidationError("成员自助配额需指定本人的凭据")

        if target_kind == "key" and target_id is None:
            raise ValidationError("platform key 配额需要 access_id 或 target_id")
        if target_kind == "system" and not is_platform_admin:
            raise ValidationError("仅平台管理员可设置 system 配额")

        period = cmd.period or "monthly"
        anchor = validate_platform_budget_upsert(
            target_kind=target_kind,
            credential_id=cmd.credential_id,
            model_name=cmd.model_name,
            period=period,
            limit_usd=cmd.limit_usd,
            limit_tokens=cmd.limit_tokens,
            limit_requests=cmd.limit_requests,
            limit_images=cmd.limit_images,
            period_timezone=cmd.period_timezone or cmd.reset_timezone,
            period_reset_minutes=cmd.period_reset_minutes
            if cmd.period_reset_minutes is not None
            else cmd.reset_time_minutes,
            period_reset_day=cmd.period_reset_day
            if cmd.period_reset_day is not None
            else cmd.reset_day_of_month,
        )

        if member_self_service:
            if actor_user_id is None:
                raise ValidationError("成员自助配额需要 actor_user_id")
            if cmd.credential_id is None:
                raise ValidationError("成员自助配额需指定本人的凭据")
            await self._assert_credential_owned_by_actor(
                cmd.credential_id,
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
            )
            if cmd.model_name:
                await self._assert_model_alias_on_credential(cmd.credential_id, cmd.model_name)
        else:
            await self._assert_budget_target_in_team(
                target_kind,
                target_id,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )
            if cmd.credential_id is not None:
                await self._assert_credential_in_team(
                    cmd.credential_id,
                    tenant_id=tenant_id,
                    is_platform_admin=is_platform_admin,
                )
                if cmd.model_name:
                    await self._assert_model_alias_on_credential(cmd.credential_id, cmd.model_name)

        budget_tenant = tenant_id if (target_kind == "user" and cmd.credential_id is None) else None
        return target_kind, target_id, budget_tenant, period, anchor

    async def _prepare_platform_upsert_item(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
        actor_user_id: uuid.UUID | None = None,
        member_self_service: bool = False,
    ) -> dict[str, object]:
        target_kind, target_id, budget_tenant, period, anchor = await self._resolve_platform_target(
            cmd,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
            actor_user_id=actor_user_id,
            member_self_service=member_self_service,
        )
        return {
            "target_kind": target_kind,
            "target_id": target_id,
            "tenant_id": budget_tenant,
            "period": period,
            "model_name": cmd.model_name,
            "credential_id": cmd.credential_id,
            "limit_usd": cmd.limit_usd,
            "soft_limit_usd": None,
            "limit_tokens": cmd.limit_tokens,
            "limit_requests": cmd.limit_requests,
            "limit_images": cmd.limit_images,
            "period_timezone": anchor.timezone,
            "period_reset_minutes": anchor.time_minutes,
            "period_reset_day": anchor.day_of_month,
            "enabled": cmd.enabled,
            "valid_from": cmd.valid_from,
            "valid_until": cmd.valid_until,
        }

    async def _upsert_platform_quota_rule(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> GatewayBudget:
        target_kind, target_id, budget_tenant, period, anchor = await self._resolve_platform_target(
            cmd, tenant_id=tenant_id, is_platform_admin=is_platform_admin
        )

        budget = (
            await self._budgets.batch_upsert(
                [
                    {
                        "target_kind": target_kind,
                        "target_id": target_id,
                        "tenant_id": budget_tenant,
                        "period": period,
                        "model_name": cmd.model_name,
                        "credential_id": cmd.credential_id,
                        "limit_usd": cmd.limit_usd,
                        "soft_limit_usd": None,
                        "limit_tokens": cmd.limit_tokens,
                        "limit_requests": cmd.limit_requests,
                        "limit_images": cmd.limit_images,
                        "period_timezone": anchor.timezone,
                        "period_reset_minutes": anchor.time_minutes,
                        "period_reset_day": anchor.day_of_month,
                        "enabled": cmd.enabled,
                        "valid_from": cmd.valid_from,
                        "valid_until": cmd.valid_until,
                    }
                ]
            )
        )[0]
        await self._maybe_index_user_credential_budget(budget)
        from domains.gateway.application.gateway_cache_invalidation import (
            invalidate_gateway_budget_config_cache,
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_budget_config_cache()
        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)
        self.invalidate_tenant_gateway_read_caches(tenant_id)
        return budget

    @staticmethod
    async def _maybe_index_user_credential_budget(budget: GatewayBudget) -> None:
        if budget.credential_id is None or budget.target_id is None:
            return
        from domains.gateway.application.user_credential_budget_index import (
            add_user_credential,
        )

        await add_user_credential(budget.target_id, budget.credential_id)

    async def _upsert_upstream_quota_rule(
        self,
        cmd: QuotaRuleUpsertCommand,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
    ) -> tuple[ProviderQuota, uuid.UUID]:
        if cmd.credential_id is None:
            raise ValidationError("upstream 配额需要 credential_id")

        display_team_id = await self._assert_upstream_credential_writable(
            cmd.credential_id,
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin,
            request_tenant_id=tenant_id,
        )

        if cmd.model_name:
            await self._assert_real_model_on_credential(cmd.credential_id, cmd.model_name)

        label = cmd.quota_label or "default"
        window_seconds = cmd.window_seconds if cmd.window_seconds is not None else 0
        reset_strategy = cmd.reset_strategy or default_reset_strategy_for_window(window_seconds)

        real_model = (
            await self._resolve_registered_real_model(cmd.credential_id, cmd.model_name)
            if cmd.model_name
            else None
        )

        reset_fields = _plan_reset_fields_from_cmd(
            cmd, window_seconds=window_seconds, reset_strategy=reset_strategy
        )

        row = await self._provider_quotas.upsert(
            credential_id=cmd.credential_id,
            real_model=real_model,
            label=label,
            window_seconds=window_seconds,
            reset_strategy=reset_strategy,
            limit_usd=cmd.limit_usd,
            limit_tokens=cmd.limit_tokens,
            limit_requests=cmd.limit_requests,
            limit_images=cmd.limit_images,
            enabled=cmd.enabled,
            valid_from=cmd.valid_from,
            valid_until=cmd.valid_until,
            **reset_fields,
        )

        return row, display_team_id

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

        reset_strategy = cmd.reset_strategy or default_reset_strategy_for_window(window_seconds)

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
                valid_from=now,
                included_models=included_models,
            )

            existing_quotas = []

        else:
            existing_quotas = await self._entitlement_plans.list_quotas(plan.id)

        from domains.gateway.application.management.plan_quota_merge import (
            merge_plan_quotas_by_label,
        )

        quota_payload: dict[str, object] = {
            "label": label,
            "window_seconds": window_seconds,
            "reset_strategy": reset_strategy,
            "limit_usd": cmd.limit_usd,
            "limit_tokens": cmd.limit_tokens,
            "limit_requests": cmd.limit_requests,
            "limit_images": cmd.limit_images,
            "enabled": cmd.enabled,
            "valid_from": cmd.valid_from,
            "valid_until": cmd.valid_until,
            **_plan_reset_fields_from_cmd(
                cmd, window_seconds=window_seconds, reset_strategy=reset_strategy
            ),
        }

        if cmd.unit_price_usd_per_token is not None:
            quota_payload["unit_price_usd_per_token"] = cmd.unit_price_usd_per_token

        if cmd.unit_price_usd_per_request is not None:
            quota_payload["unit_price_usd_per_request"] = cmd.unit_price_usd_per_request

        merged = merge_plan_quotas_by_label(
            existing_quotas,
            label,
            quota_payload,
            extra_fields=("unit_price_usd_per_token", "unit_price_usd_per_request"),
        )

        await self._entitlement_plans.replace_quotas(plan.id, merged)

        return plan


__all__ = [
    "QuotaRuleBatchFailure",
    "QuotaRuleBatchResult",
    "QuotaRuleUpsertCommand",
    "QuotaRuleUpsertResult",
    "QuotaRuleWritesMixin",
]
