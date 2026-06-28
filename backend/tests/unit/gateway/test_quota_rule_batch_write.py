"""配额规则 batch 写入路由单测。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management import GatewayManagementWriteService
from domains.gateway.application.quota.management.quota_rule_writes import (
    QuotaRuleUpsertCommand,
)
from domains.tenancy.application.ports import GatewayTeamMembershipSnapshot


def _writes() -> GatewayManagementWriteService:
    return GatewayManagementWriteService(MagicMock())


def _mock_upstream_row(*, cred_id: uuid.UUID, rule_id: uuid.UUID | None = None) -> MagicMock:
    row = MagicMock()
    row.id = rule_id or uuid.uuid4()
    row.credential_id = cred_id
    row.real_model = "gpt-4o"
    row.label = "default"
    row.window_seconds = 0
    row.reset_strategy = "rolling"
    row.reset_timezone = "UTC"
    row.reset_time_minutes = 0
    row.reset_day_of_month = 1
    row.limit_usd = Decimal("10")
    row.limit_tokens = None
    row.limit_requests = None
    row.enabled = True
    row.valid_from = None
    row.valid_until = None
    return row


@pytest.mark.asyncio
async def test_admin_batch_accepts_upstream_with_actor_user_id() -> None:
    """管理员 batch 传 actor_user_id 时 upstream 仍应写入，而非误判为成员自助。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    cred_id = uuid.uuid4()

    svc._upsert_upstream_quota_rule = AsyncMock(  # type: ignore[method-assign]
        return_value=(_mock_upstream_row(cred_id=cred_id), tenant_id)
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

    personal_team_id = uuid.uuid4()
    svc._upsert_upstream_quota_rule = AsyncMock(  # type: ignore[method-assign]
        return_value=(_mock_upstream_row(cred_id=cred_id), personal_team_id)
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
    provider_quota_cache_invalidated = False

    async def _record_invalidate(team_id: uuid.UUID) -> None:
        invalidated.append(team_id)

    async def _record_provider_quota_invalidate() -> None:
        nonlocal provider_quota_cache_invalidated
        provider_quota_cache_invalidated = True

    import domains.gateway.application.observability.gateway_cache_invalidation as cache_mod

    original = cache_mod.invalidate_gateway_quota_rule_cache_for_team
    original_pp = cache_mod.invalidate_gateway_provider_quota_config_cache
    cache_mod.invalidate_gateway_quota_rule_cache_for_team = _record_invalidate
    cache_mod.invalidate_gateway_provider_quota_config_cache = _record_provider_quota_invalidate
    try:
        await svc._invalidate_quota_rule_list_cache(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            upstream_changed=True,
        )
    finally:
        cache_mod.invalidate_gateway_quota_rule_cache_for_team = original
        cache_mod.invalidate_gateway_provider_quota_config_cache = original_pp

    assert provider_quota_cache_invalidated
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
    svc._provider_quotas.upsert = AsyncMock(return_value=_mock_upstream_row(cred_id=cred_id))  # type: ignore[method-assign]

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
    svc._provider_quotas.upsert.assert_awaited_once()
