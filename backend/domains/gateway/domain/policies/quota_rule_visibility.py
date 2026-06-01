"""配额规则成员可见性（纯函数，无 I/O）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from domains.gateway.domain.policies.budget_scope_policy import (
    BudgetTeamContext,
    budget_target_allowed,
)

if TYPE_CHECKING:
    from uuid import UUID

QuotaRuleVisibilityLayer = Literal["platform", "upstream", "downstream"]
QuotaRuleVisibilityAccessKind = Literal["none", "vkey", "apikey_grant"]


@dataclass(frozen=True)
class QuotaRuleVisibilityKey:
    layer: QuotaRuleVisibilityLayer
    user_id: UUID | None
    target_kind: str | None
    target_id: UUID | None
    access_kind: QuotaRuleVisibilityAccessKind
    access_id: UUID | None
    credential_id: UUID | None


@dataclass(frozen=True)
class QuotaRuleVisibilityContext:
    team_id: UUID
    actor_user_id: UUID | None
    is_team_admin: bool
    is_platform_admin: bool
    member_user_ids: frozenset[UUID]
    visible_vkey_ids: frozenset[UUID]
    visible_credential_ids: frozenset[UUID]


def quota_rule_visible_to_member(
    key: QuotaRuleVisibilityKey,
    ctx: QuotaRuleVisibilityContext,
) -> bool:
    if ctx.is_team_admin:
        return True

    if key.layer == "platform":
        return _platform_rule_visible(key, ctx)
    if key.layer == "upstream":
        return key.credential_id is not None and key.credential_id in ctx.visible_credential_ids
    if key.layer == "downstream":
        if key.access_kind == "vkey":
            return key.access_id is not None and key.access_id in ctx.visible_vkey_ids
        return False

    return False


def filter_quota_rules_for_member(
    keys: list[QuotaRuleVisibilityKey],
    ctx: QuotaRuleVisibilityContext,
) -> list[bool]:
    return [quota_rule_visible_to_member(key, ctx) for key in keys]


def member_user_budget_visible_in_team(
    *,
    credential_id: UUID | None,
    budget_tenant_id: UUID | None,
    team_id: UUID,
    visible_credential_ids: frozenset[UUID],
) -> bool:
    """成员 ``user`` 预算行在当前团队是否可见（团队轴收敛，纯规则）。

    - 总量 / 模型护栏（``credential_id`` 为空）：按团队隔离，须 ``budget_tenant_id == team_id``；
    - 成员 + 凭据(+模型)：凭据天然绑定团队，须 ``credential_id`` 落在团队可见凭据集合内，
      避免同一用户在他团队的凭据级预算行跨团队泄漏。
    """
    if credential_id is None:
        return budget_tenant_id == team_id
    return credential_id in visible_credential_ids


def _platform_rule_visible(
    key: QuotaRuleVisibilityKey,
    ctx: QuotaRuleVisibilityContext,
) -> bool:
    target_kind = key.target_kind or "tenant"

    if target_kind == "tenant":
        return True

    if target_kind == "user":
        return key.user_id == ctx.actor_user_id

    if target_kind == "key":
        vkey_id = key.access_id if key.access_kind == "vkey" else key.target_id
        return vkey_id is not None and vkey_id in ctx.visible_vkey_ids

    team_ctx = BudgetTeamContext(
        tenant_id=ctx.team_id,
        member_user_ids=ctx.member_user_ids,
        is_platform_admin=ctx.is_platform_admin,
    )
    key_belongs = (
        key.target_id in ctx.visible_vkey_ids if target_kind == "key" and key.target_id else None
    )
    return budget_target_allowed(
        target_kind,
        key.target_id,
        team_ctx,
        key_belongs_to_team=key_belongs,
    )


__all__ = [
    "QuotaRuleVisibilityContext",
    "QuotaRuleVisibilityKey",
    "filter_quota_rules_for_member",
    "member_user_budget_visible_in_team",
    "quota_rule_visible_to_member",
]
