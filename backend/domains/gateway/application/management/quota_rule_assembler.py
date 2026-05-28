"""团队配额规则聚合 Assembler（管理面读路径）。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from domains.gateway.application.management.quota_rule_cache import (
    build_actor_role_hash,
    get_cached_quota_rules,
    put_cached_quota_rules,
)
from domains.gateway.application.management.quota_rule_read_mappers import (
    budget_to_quota_rule,
    filter_quota_rules,
    flatten_entitlement_plan,
    flatten_provider_plan,
)
from domains.gateway.application.management.quota_rule_read_model import (
    QuotaRuleListFilters,
    QuotaRuleReadModel,
)
from domains.gateway.domain.policies.quota_rule_visibility import (
    QuotaRuleVisibilityContext,
    QuotaRuleVisibilityKey,
    quota_rule_visible_to_member,
)

if TYPE_CHECKING:
    from domains.gateway.application.management.reads import GatewayManagementReadService


async def assemble_team_quota_rules(
    reads: GatewayManagementReadService,
    team_id: UUID,
    *,
    actor_user_id: UUID | None,
    team_role: str,
    is_platform_admin: bool,
    is_team_admin: bool,
    filters: QuotaRuleListFilters | None = None,
) -> list[QuotaRuleReadModel]:
    """聚合 platform budget + upstream provider + downstream entitlement 规则。"""
    actor_role_hash = build_actor_role_hash(
        is_team_admin=is_team_admin,
        is_platform_admin=is_platform_admin,
        team_role=team_role,
    )
    cached = await get_cached_quota_rules(
        team_id,
        actor_role_hash=actor_role_hash,
        filters=filters,
    )
    if cached is not None:
        return cached

    rules: list[QuotaRuleReadModel] = []

    if is_team_admin:
        budgets = await reads.list_budgets_for_team_admin(
            team_id,
            include_system=is_platform_admin,
        )
    else:
        budgets = await reads.list_budgets_for_tenant_and_user(
            team_id,
            actor_user_id,
            actor_user_id=actor_user_id,
        )
    rules.extend(budget_to_quota_rule(b, team_id=team_id) for b in budgets)

    creds = await reads.list_credential_summaries_for_team(
        team_id,
        user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )
    visible_credential_ids = frozenset(c.id for c in creds)
    if creds:
        plans_by_cred = await reads.list_provider_plans_with_quotas_for_credentials(
            [c.id for c in creds]
        )
        for cred in creds:
            for plan in plans_by_cred.get(cred.id, ()):
                rules.extend(flatten_provider_plan(plan, team_id=team_id))

    vkeys = await reads.list_virtual_keys_for_team(
        team_id,
        actor_user_id=actor_user_id,
        team_role=team_role,
        is_platform_admin=is_platform_admin,
    )
    visible_vkey_ids = frozenset(v.id for v in vkeys)
    if vkeys:
        plans_by_vkey = await reads.list_entitlement_plans_with_quotas_for_vkeys(
            [v.id for v in vkeys]
        )
        for vkey in vkeys:
            for plan in plans_by_vkey.get(vkey.id, ()):
                rules.extend(flatten_entitlement_plan(plan, team_id=team_id))

    if not is_team_admin:
        member_user_ids = await reads.list_team_member_user_ids(team_id)
        visibility_ctx = QuotaRuleVisibilityContext(
            team_id=team_id,
            actor_user_id=actor_user_id,
            is_team_admin=False,
            is_platform_admin=is_platform_admin,
            member_user_ids=member_user_ids,
            visible_vkey_ids=visible_vkey_ids,
            visible_credential_ids=visible_credential_ids,
        )
        rules = [
            rule
            for rule in rules
            if quota_rule_visible_to_member(
                _visibility_key(rule),
                visibility_ctx,
            )
        ]

    if filters is not None:
        rules = filter_quota_rules(
            rules,
            layer=filters.layer,
            user_id=filters.user_id,
            credential_id=filters.credential_id,
            model_name=filters.model_name,
            period=filters.period,
        )

    await put_cached_quota_rules(
        team_id,
        rules,
        actor_role_hash=actor_role_hash,
        filters=filters,
    )
    return rules


def _visibility_key(rule: QuotaRuleReadModel) -> QuotaRuleVisibilityKey:
    return QuotaRuleVisibilityKey(
        layer=rule.key.layer,
        user_id=rule.key.user_id,
        target_kind=rule.key.target_kind,
        target_id=rule.key.target_id,
        access_kind=rule.key.access_kind,
        access_id=rule.key.access_id,
        credential_id=rule.key.credential_id,
    )


__all__ = ["assemble_team_quota_rules"]
