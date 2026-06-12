"""配额规则 batch 写入路由单测。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.write_modules import GatewayManagementWriteService
from domains.gateway.application.management.write_modules.quota_rule_writes import (
    QuotaRuleUpsertCommand,
)
from domains.tenancy.application.ports import GatewayTeamMembershipSnapshot


def _writes() -> GatewayManagementWriteService:
    return GatewayManagementWriteService(MagicMock())


@pytest.mark.asyncio
async def test_admin_batch_accepts_upstream_with_actor_user_id() -> None:
    """管理员 batch 传 actor_user_id 时 upstream 仍应写入，而非误判为成员自助。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    mock_plan = MagicMock()
    mock_plan.id = plan_id
    mock_plan.credential_id = cred_id
    mock_plan.real_model = "gpt-4o"
    mock_plan.label = "auto"
    mock_plan.is_active = True
    mock_plan.quotas = []

    svc.upsert_quota_rule = AsyncMock(return_value=mock_plan)  # type: ignore[method-assign]
    svc._provider_plans.get_with_quotas = AsyncMock(  # type: ignore[method-assign]
        return_value=(
            MagicMock(
                id=plan_id,
                credential_id=cred_id,
                real_model="gpt-4o",
                label="auto",
                is_active=True,
            ),
            [
                MagicMock(
                    id=uuid.uuid4(),
                    label="default",
                    window_seconds=0,
                    reset_strategy="rolling",
                    limit_usd=Decimal("10"),
                    limit_tokens=None,
                    limit_requests=None,
                    unit_price_usd_per_token=None,
                    unit_price_usd_per_request=None,
                )
            ],
        )
    )
    svc._creds.get = AsyncMock(return_value=MagicMock(tenant_id=tenant_id))  # type: ignore[method-assign]
    svc._invalidate_quota_rule_list_cache = AsyncMock()  # type: ignore[method-assign]

    result = await svc.batch_upsert_quota_rules(
        [
            QuotaRuleUpsertCommand(
                layer="upstream",
                credential_id=cred_id,
                model_name="gpt-4o",
                limit_usd=Decimal("10"),
            )
        ],
        tenant_id=tenant_id,
        is_platform_admin=False,
        actor_user_id=actor_user_id,
        member_self_service=False,
    )

    assert result.failed == []
    assert len(result.succeeded) == 1
    svc.upsert_quota_rule.assert_awaited_once()
    svc._invalidate_quota_rule_list_cache.assert_awaited_once_with(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        upstream_changed=True,
    )


@pytest.mark.asyncio
async def test_member_self_batch_rejects_upstream() -> None:
    svc = _writes()
    svc._invalidate_quota_rule_list_cache = AsyncMock()  # type: ignore[method-assign]

    result = await svc.batch_upsert_quota_rules(
        [
            QuotaRuleUpsertCommand(
                layer="upstream",
                credential_id=uuid.uuid4(),
                limit_usd=Decimal("10"),
            )
        ],
        tenant_id=uuid.uuid4(),
        is_platform_admin=False,
        actor_user_id=uuid.uuid4(),
        member_self_service=True,
    )

    assert result.succeeded == []
    assert len(result.failed) == 1
    assert "成员自助" in result.failed[0].error
    svc._invalidate_quota_rule_list_cache.assert_not_awaited()


@pytest.mark.asyncio
async def test_upstream_cache_invalidates_all_membership_teams() -> None:
    svc = _writes()
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    other_team_id = uuid.uuid4()

    svc._teams.list_gateway_team_memberships = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            GatewayTeamMembershipSnapshot(
                team_id=tenant_id,
                kind="shared",
                role="admin",
            ),
            GatewayTeamMembershipSnapshot(
                team_id=other_team_id,
                kind="shared",
                role="admin",
            ),
        ]
    )

    invalidated: list[uuid.UUID] = []

    async def _record_invalidate(team_id: uuid.UUID) -> None:
        invalidated.append(team_id)

    import domains.gateway.application.gateway_cache_invalidation as cache_mod

    original = cache_mod.invalidate_gateway_quota_rule_cache_for_team
    cache_mod.invalidate_gateway_quota_rule_cache_for_team = _record_invalidate
    try:
        await svc._invalidate_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            upstream_changed=True,
        )
    finally:
        cache_mod.invalidate_gateway_quota_rule_cache_for_team = original

    assert set(invalidated) == {tenant_id, other_team_id}
