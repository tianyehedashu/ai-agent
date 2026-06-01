"""Quota rule visibility policy 单元测试。"""

from __future__ import annotations

import uuid

from domains.gateway.domain.policies.quota_rule_visibility import (
    QuotaRuleVisibilityContext,
    QuotaRuleVisibilityKey,
    member_user_budget_visible_in_team,
    quota_rule_visible_to_member,
)


def test_member_guardrail_budget_visible_only_in_own_team() -> None:
    team = uuid.uuid4()
    assert member_user_budget_visible_in_team(
        credential_id=None,
        budget_tenant_id=team,
        team_id=team,
        visible_credential_ids=frozenset(),
    )
    assert not member_user_budget_visible_in_team(
        credential_id=None,
        budget_tenant_id=uuid.uuid4(),
        team_id=team,
        visible_credential_ids=frozenset(),
    )


def test_member_credential_budget_gated_by_visible_credentials() -> None:
    team = uuid.uuid4()
    own_cred = uuid.uuid4()
    assert member_user_budget_visible_in_team(
        credential_id=own_cred,
        budget_tenant_id=None,
        team_id=team,
        visible_credential_ids=frozenset({own_cred}),
    )
    # 他团队凭据的成员预算行：凭据不在可见集合内 → 不可见。
    assert not member_user_budget_visible_in_team(
        credential_id=uuid.uuid4(),
        budget_tenant_id=None,
        team_id=team,
        visible_credential_ids=frozenset({own_cred}),
    )


def _ctx(
    *,
    actor_user_id: uuid.UUID | None = None,
    visible_vkey_ids: frozenset[uuid.UUID] | None = None,
    visible_credential_ids: frozenset[uuid.UUID] | None = None,
) -> QuotaRuleVisibilityContext:
    team_id = uuid.uuid4()
    return QuotaRuleVisibilityContext(
        team_id=team_id,
        actor_user_id=actor_user_id,
        is_team_admin=False,
        is_platform_admin=False,
        member_user_ids=frozenset({actor_user_id} if actor_user_id else set()),
        visible_vkey_ids=visible_vkey_ids or frozenset(),
        visible_credential_ids=visible_credential_ids or frozenset(),
    )


def test_member_sees_tenant_platform_rule() -> None:
    ctx = _ctx(actor_user_id=uuid.uuid4())
    key = QuotaRuleVisibilityKey(
        layer="platform",
        user_id=None,
        target_kind="tenant",
        target_id=ctx.team_id,
        access_kind="none",
        access_id=None,
        credential_id=None,
    )
    assert quota_rule_visible_to_member(key, ctx) is True


def test_member_sees_own_user_platform_rule() -> None:
    user_id = uuid.uuid4()
    ctx = _ctx(actor_user_id=user_id)
    key = QuotaRuleVisibilityKey(
        layer="platform",
        user_id=user_id,
        target_kind="user",
        target_id=user_id,
        access_kind="none",
        access_id=None,
        credential_id=None,
    )
    assert quota_rule_visible_to_member(key, ctx) is True


def test_member_hides_other_user_platform_rule() -> None:
    actor_id = uuid.uuid4()
    other_id = uuid.uuid4()
    ctx = _ctx(actor_user_id=actor_id)
    key = QuotaRuleVisibilityKey(
        layer="platform",
        user_id=other_id,
        target_kind="user",
        target_id=other_id,
        access_kind="none",
        access_id=None,
        credential_id=None,
    )
    assert quota_rule_visible_to_member(key, ctx) is False


def test_member_sees_own_user_credential_platform_rule() -> None:
    user_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    ctx = _ctx(actor_user_id=user_id, visible_credential_ids=frozenset({cred_id}))
    key = QuotaRuleVisibilityKey(
        layer="platform",
        user_id=user_id,
        target_kind="user",
        target_id=user_id,
        access_kind="none",
        access_id=None,
        credential_id=cred_id,
    )
    assert quota_rule_visible_to_member(key, ctx) is True


def test_member_hides_other_user_credential_rule_even_if_credential_visible() -> None:
    actor_id = uuid.uuid4()
    other_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    # 凭据对本成员可见，也不得因此看到他人的「成员+凭据」限额（防 credential_id 过滤枚举）。
    ctx = _ctx(actor_user_id=actor_id, visible_credential_ids=frozenset({cred_id}))
    key = QuotaRuleVisibilityKey(
        layer="platform",
        user_id=other_id,
        target_kind="user",
        target_id=other_id,
        access_kind="none",
        access_id=None,
        credential_id=cred_id,
    )
    assert quota_rule_visible_to_member(key, ctx) is False


def test_member_sees_visible_upstream_rule() -> None:
    cred_id = uuid.uuid4()
    ctx = _ctx(visible_credential_ids=frozenset({cred_id}))
    key = QuotaRuleVisibilityKey(
        layer="upstream",
        user_id=None,
        target_kind=None,
        target_id=None,
        access_kind="none",
        access_id=None,
        credential_id=cred_id,
    )
    assert quota_rule_visible_to_member(key, ctx) is True


def test_member_hides_invisible_upstream_rule() -> None:
    ctx = _ctx(visible_credential_ids=frozenset())
    key = QuotaRuleVisibilityKey(
        layer="upstream",
        user_id=None,
        target_kind=None,
        target_id=None,
        access_kind="none",
        access_id=None,
        credential_id=uuid.uuid4(),
    )
    assert quota_rule_visible_to_member(key, ctx) is False


def test_member_sees_visible_downstream_vkey_rule() -> None:
    vkey_id = uuid.uuid4()
    ctx = _ctx(visible_vkey_ids=frozenset({vkey_id}))
    key = QuotaRuleVisibilityKey(
        layer="downstream",
        user_id=None,
        target_kind=None,
        target_id=None,
        access_kind="vkey",
        access_id=vkey_id,
        credential_id=None,
    )
    assert quota_rule_visible_to_member(key, ctx) is True
