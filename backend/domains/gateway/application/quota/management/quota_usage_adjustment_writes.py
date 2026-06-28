"""配额用量手工校正写路径。"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from domains.gateway.application.management.write_base import (
    GatewayManagementWriteBaseMixin,
)
from domains.gateway.application.quota.management.quota_usage_adjustment import (
    QuotaUsageAdjustmentCommand,
    apply_quota_usage_adjustment,
)
from domains.gateway.application.quota.management.quota_usage_snapshot import (
    enrich_quota_rules_with_usage,
)
from domains.gateway.infrastructure.repositories.budget_repository import BudgetRepository
from libs.exceptions import NotFoundError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from domains.gateway.application.quota.management.quota_rule_read_model import (
        QuotaRuleReadModel,
    )


class QuotaUsageAdjustmentWritesMixin(GatewayManagementWriteBaseMixin):
    async def adjust_quota_rule_usage(
        self,
        cmd: QuotaUsageAdjustmentCommand,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        is_team_admin: bool,
        member_self_service: bool = False,
    ) -> QuotaRuleReadModel:
        await self._assert_can_adjust_usage(
            cmd,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin,
            is_team_admin=is_team_admin,
            member_self_service=member_self_service,
        )
        await apply_quota_usage_adjustment(self._session, cmd)
        await self._session.commit()

        from domains.gateway.application.observability.gateway_cache_invalidation import (
            invalidate_gateway_quota_rule_cache_for_team,
        )

        await invalidate_gateway_quota_rule_cache_for_team(tenant_id)

        rule = await self._load_rule_after_adjustment(cmd, tenant_id=tenant_id)
        enriched = await enrich_quota_rules_with_usage([rule], session=self._session)
        return enriched[0]

    async def set_quota_rule_enabled(
        self,
        *,
        layer: str,
        budget_id: uuid.UUID | None,
        plan_id: uuid.UUID | None,
        quota_id: uuid.UUID | None,
        enabled: bool,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        is_team_admin: bool,
        member_self_service: bool = False,
    ) -> QuotaRuleReadModel:
        """启用 / 停用单条配额规则（鉴权口径与用量校正一致）。"""
        auth_cmd = QuotaUsageAdjustmentCommand(
            layer=layer,  # type: ignore[arg-type]
            budget_id=budget_id,
            plan_id=plan_id,
            quota_id=quota_id,
        )
        await self._assert_can_adjust_usage(
            auth_cmd,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            is_platform_admin=is_platform_admin,
            is_team_admin=is_team_admin,
            member_self_service=member_self_service,
        )

        if layer == "platform":
            if budget_id is None:
                raise ValidationError("platform 启用停用需要 budget_id")
            budget = await self._budgets.get(budget_id)
            if budget is None:
                raise NotFoundError(f"预算不存在: {budget_id}")
            budget.enabled = enabled
            await self._session.flush()
        elif layer == "upstream":
            rule_id = quota_id or plan_id
            if rule_id is None:
                raise ValidationError("upstream 启用停用需要 quota_id")
            ok = await self._provider_quotas.set_enabled(rule_id, enabled=enabled)
            if not ok:
                raise NotFoundError(f"配额规则不存在: {rule_id}")
        elif layer == "downstream":
            if plan_id is None or quota_id is None:
                raise ValidationError(f"{layer} 启用停用需要 plan_id 与 quota_id")
            ok = await self._entitlement_plans.set_quota_enabled(plan_id, quota_id, enabled=enabled)
            if not ok:
                raise NotFoundError(f"配额规则不存在: {quota_id}")
        else:
            raise ValidationError(f"不支持的配额层级: {layer}")

        await self._session.commit()

        from domains.gateway.application.observability.gateway_cache_invalidation import (
            invalidate_gateway_budget_config_cache,
        )

        if layer == "platform":
            await invalidate_gateway_budget_config_cache()
            await self._invalidate_quota_rule_list_cache(
                tenant_id=tenant_id, actor_user_id=actor_user_id
            )
        else:
            await self._invalidate_quota_rule_list_cache(
                tenant_id=tenant_id,
                actor_user_id=actor_user_id,
                upstream_changed=(layer == "upstream"),
            )

        rule = await self._load_rule_after_adjustment(auth_cmd, tenant_id=tenant_id)
        enriched = await enrich_quota_rules_with_usage([rule], session=self._session)
        return enriched[0]

    async def _assert_can_adjust_usage(
        self,
        cmd: QuotaUsageAdjustmentCommand,
        *,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        is_platform_admin: bool,
        is_team_admin: bool,
        member_self_service: bool,
    ) -> None:
        if member_self_service:
            if cmd.layer == "platform":
                if cmd.budget_id is None:
                    raise ValidationError("platform 用量校正需要 budget_id")
                budget = await self._budgets.get(cmd.budget_id)
                if budget is None:
                    raise NotFoundError(f"预算不存在: {cmd.budget_id}")
                if budget.target_kind != "user" or budget.target_id != actor_user_id:
                    raise PermissionDeniedError("仅可调整本人的平台配额用量")
                if budget.credential_id is not None:
                    await self._assert_credential_owned_by_actor(
                        budget.credential_id,
                        actor_user_id=actor_user_id,
                    )
                return
            if cmd.layer == "upstream":
                rule_id = cmd.quota_id or cmd.plan_id
                if rule_id is None:
                    raise ValidationError("upstream 用量校正需要 quota_id")
                row = await self._provider_quotas.get(rule_id)
                if row is None:
                    raise NotFoundError(f"上游配额不存在: {rule_id}")
                await self._assert_upstream_credential_writable(
                    row.credential_id,
                    actor_user_id=actor_user_id,
                    is_platform_admin=False,
                    request_tenant_id=tenant_id,
                )
                return
            raise PermissionDeniedError("成员自助仅可调整本人平台或本人凭据的上游配额用量")

        if not is_team_admin and not is_platform_admin:
            raise PermissionDeniedError("需要团队管理员权限")

        if cmd.layer == "platform":
            if cmd.budget_id is None:
                raise ValidationError("platform 用量校正需要 budget_id")
            await self._assert_budget_in_team(
                cmd.budget_id,
                tenant_id=tenant_id,
                is_platform_admin=is_platform_admin,
            )
            return

        if cmd.layer == "upstream":
            rule_id = cmd.quota_id or cmd.plan_id
            if rule_id is None:
                raise ValidationError("upstream 用量校正需要 quota_id")
            row = await self._provider_quotas.get(rule_id)
            if row is None:
                raise NotFoundError(f"上游配额不存在: {rule_id}")
            await self._assert_upstream_credential_writable(
                row.credential_id,
                actor_user_id=actor_user_id,
                is_platform_admin=is_platform_admin,
                request_tenant_id=tenant_id,
            )
            return

        if cmd.plan_id is None or cmd.quota_id is None:
            raise ValidationError(f"{cmd.layer} 用量校正需要 plan_id 与 quota_id")

        await self._assert_entitlement_plan_in_team(
            cmd.plan_id,
            tenant_id=tenant_id,
            is_platform_admin=is_platform_admin,
        )

    async def _load_rule_after_adjustment(
        self,
        cmd: QuotaUsageAdjustmentCommand,
        *,
        tenant_id: uuid.UUID,
    ) -> QuotaRuleReadModel:
        from domains.gateway.application.quota.management.plan_read_mappers import (
            entitlement_plan_from_orm,
            provider_quota_from_orm,
        )
        from domains.gateway.application.quota.management.quota_rule_read_mappers import (
            budget_to_quota_rule,
            flatten_entitlement_plan,
            provider_quota_to_quota_rule,
        )

        if cmd.layer == "platform":
            if cmd.budget_id is None:
                raise ValidationError("platform 用量校正需要 budget_id")
            budget = await BudgetRepository(self._session).get(cmd.budget_id)
            if budget is None:
                raise NotFoundError(f"预算不存在: {cmd.budget_id}")
            return budget_to_quota_rule(budget, team_id=tenant_id)

        if cmd.layer == "upstream":
            rule_id = cmd.quota_id or cmd.plan_id
            if rule_id is None:
                raise ValidationError("upstream 用量校正需要 quota_id")
            row = await self._provider_quotas.get(rule_id)
            if row is None:
                raise NotFoundError(f"上游配额不存在: {rule_id}")
            read_model = provider_quota_from_orm(row)
            return provider_quota_to_quota_rule(read_model, team_id=tenant_id)

        if cmd.plan_id is None or cmd.quota_id is None:
            raise ValidationError(f"{cmd.layer} 用量校正需要 plan_id 与 quota_id")

        row = await self._entitlement_plans.get_with_quotas(cmd.plan_id)
        if row is None:
            raise NotFoundError(f"下游套餐不存在: {cmd.plan_id}")
        plan, quotas = row
        read_model = entitlement_plan_from_orm(plan, quotas)
        rules = flatten_entitlement_plan(read_model, team_id=tenant_id)

        matched = next(
            (r for r in rules if r.source_ref.quota_id == cmd.quota_id),
            None,
        )
        if matched is None:
            raise NotFoundError(f"配额规则不存在: {cmd.quota_id}")
        return matched


__all__ = ["QuotaUsageAdjustmentWritesMixin"]
