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

    svc._upsert_upstream_quota_rule = AsyncMock(  # type: ignore[method-assign]
        return_value=(mock_plan, tenant_id)
    )
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
    svc._upsert_upstream_quota_rule.assert_awaited_once()
    svc._invalidate_quota_rule_list_cache.assert_awaited_once_with(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        upstream_changed=True,
    )


@pytest.mark.asyncio
async def test_member_self_batch_accepts_personal_upstream() -> None:
    """成员自助：本人 BYOK 可写 upstream 厂商额度。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    mock_plan = MagicMock()
    mock_plan.id = plan_id

    personal_team_id = uuid.uuid4()
    svc._upsert_upstream_quota_rule = AsyncMock(  # type: ignore[method-assign]
        return_value=(mock_plan, personal_team_id)
    )
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
        member_self_service=True,
    )

    assert result.failed == []
    assert len(result.succeeded) == 1
    svc._upsert_upstream_quota_rule.assert_awaited_once()


@pytest.mark.asyncio
async def test_member_self_batch_rejects_downstream() -> None:
    svc = _writes()
    svc._invalidate_quota_rule_list_cache = AsyncMock()  # type: ignore[method-assign]

    result = await svc.batch_upsert_quota_rules(
        [
            QuotaRuleUpsertCommand(
                layer="downstream",
                access_kind="vkey",
                access_id=uuid.uuid4(),
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
    provider_plan_cache_invalidated = False

    async def _record_invalidate(team_id: uuid.UUID) -> None:
        invalidated.append(team_id)

    async def _record_provider_plan_invalidate() -> None:
        nonlocal provider_plan_cache_invalidated
        provider_plan_cache_invalidated = True

    import domains.gateway.application.gateway_cache_invalidation as cache_mod

    original = cache_mod.invalidate_gateway_quota_rule_cache_for_team
    original_pp = cache_mod.invalidate_gateway_provider_plan_config_cache
    cache_mod.invalidate_gateway_quota_rule_cache_for_team = _record_invalidate
    cache_mod.invalidate_gateway_provider_plan_config_cache = _record_provider_plan_invalidate
    try:
        await svc._invalidate_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            upstream_changed=True,
        )
    finally:
        cache_mod.invalidate_gateway_quota_rule_cache_for_team = original
        cache_mod.invalidate_gateway_provider_plan_config_cache = original_pp

    assert provider_plan_cache_invalidated
    assert set(invalidated) == {tenant_id, other_team_id}


@pytest.mark.asyncio
async def test_upsert_upstream_validates_real_model_on_credential() -> None:
    """上游配额写入前校验 real_model 已在凭据注册。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    svc._assert_upstream_credential_writable = AsyncMock(return_value=tenant_id)  # type: ignore[method-assign]
    svc._assert_real_model_on_credential = AsyncMock()  # type: ignore[method-assign]
    svc._resolve_registered_real_model = AsyncMock(return_value="gpt-4o")  # type: ignore[method-assign]
    svc._provider_plans.get_active_for_credential_model = AsyncMock(return_value=None)  # type: ignore[method-assign]
    svc._provider_plans.create = AsyncMock()  # type: ignore[method-assign]
    svc._provider_plans.list_quotas = AsyncMock(return_value=[])  # type: ignore[method-assign]
    svc._provider_plans.replace_quotas = AsyncMock()  # type: ignore[method-assign]

    await svc._upsert_upstream_quota_rule(
        QuotaRuleUpsertCommand(
            layer="upstream",
            credential_id=cred_id,
            model_name="gpt-4o",
            limit_usd=Decimal("10"),
        ),
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        is_platform_admin=False,
    )

    svc._assert_real_model_on_credential.assert_awaited_once_with(cred_id, "gpt-4o")


@pytest.mark.asyncio
async def test_create_provider_plan_validates_real_model_on_credential() -> None:
    """凭据 API 创建 ProviderPlan 时校验 real_model 已在凭据注册。"""
    from datetime import UTC, datetime, timedelta

    svc = _writes()
    tenant_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    now = datetime.now(UTC)

    svc._assert_credential_in_team = AsyncMock()  # type: ignore[method-assign]
    svc._assert_real_model_on_credential = AsyncMock()  # type: ignore[method-assign]
    svc._resolve_registered_real_model = AsyncMock(return_value="openai/gpt-4o-mini")  # type: ignore[method-assign]
    svc._provider_plans.create = AsyncMock(return_value=MagicMock(id=uuid.uuid4()))  # type: ignore[method-assign]
    svc._invalidate_upstream_quota_rule_list_cache = AsyncMock()  # type: ignore[method-assign]

    await svc.create_provider_plan(
        credential_id=cred_id,
        tenant_id=tenant_id,
        is_platform_admin=False,
        real_model="openai/gpt-4o-mini",
        label="pack",
        valid_from=now,
        valid_until=now + timedelta(days=30),
    )

    svc._resolve_registered_real_model.assert_awaited_once_with(cred_id, "openai/gpt-4o-mini")


@pytest.mark.asyncio
async def test_create_provider_plan_normalizes_quota_reset_anchor() -> None:
    """凭据 API 直接创建 ProviderPlan 时同样写入归一化后的周期锚点。"""
    from datetime import UTC, datetime, timedelta

    svc = _writes()
    tenant_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    now = datetime.now(UTC)

    svc._assert_credential_in_team = AsyncMock()  # type: ignore[method-assign]
    svc._provider_plans.create = AsyncMock(return_value=MagicMock(id=plan_id))  # type: ignore[method-assign]
    svc._provider_plans.add_quota = AsyncMock()  # type: ignore[method-assign]
    svc._invalidate_upstream_quota_rule_list_cache = AsyncMock()  # type: ignore[method-assign]

    await svc.create_provider_plan(
        credential_id=cred_id,
        tenant_id=tenant_id,
        is_platform_admin=False,
        real_model=None,
        label="pack",
        valid_from=now,
        valid_until=now + timedelta(days=30),
        quotas=[
            {
                "label": "daily",
                "window_seconds": 86400,
                "reset_strategy": "calendar_daily_utc",
                "limit_requests": 100,
                "reset_timezone": "Asia/Shanghai",
                "reset_time_minutes": 540,
                "reset_day_of_month": 15,
            }
        ],
    )

    kwargs = svc._provider_plans.add_quota.await_args.kwargs
    assert kwargs["plan_id"] == plan_id
    assert kwargs["reset_timezone"] == "Asia/Shanghai"
    assert kwargs["reset_time_minutes"] == 540
    assert kwargs["reset_day_of_month"] == 1
