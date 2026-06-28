"""平台「成员+凭据+模型」配额写入校验链单测（_resolve_platform_target）。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management import GatewayManagementWriteService
from domains.gateway.application.quota.management.quota_rule_writes import (
    QuotaRuleUpsertCommand,
)
from libs.exceptions import ValidationError


def _writes() -> GatewayManagementWriteService:
    svc = GatewayManagementWriteService(MagicMock())
    svc._assert_budget_target_in_team = AsyncMock()  # type: ignore[method-assign]
    svc._assert_credential_in_team = AsyncMock()  # type: ignore[method-assign]
    svc._assert_credential_owned_by_actor = AsyncMock()  # type: ignore[method-assign]
    svc._assert_model_alias_on_credential = AsyncMock()  # type: ignore[method-assign]
    return svc


@pytest.mark.asyncio
async def test_user_credential_model_runs_full_assert_chain() -> None:
    svc = _writes()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="user",
        user_id=user_id,
        credential_id=cred_id,
        model_name="gpt-4--abc",
        period="monthly",
        limit_usd=Decimal("50"),
    )

    kind, target_id, budget_tenant, period, _anchor = await svc._resolve_platform_target(
        cmd, tenant_id=tenant_id, is_platform_admin=False
    )

    # 成员+凭据行由 credential 绑定团队，budget_tenant 留空（仅成员总量/模型护栏带 tenant）。
    assert (kind, target_id, budget_tenant, period) == ("user", user_id, None, "monthly")
    svc._assert_budget_target_in_team.assert_awaited_once()
    svc._assert_credential_in_team.assert_awaited_once()
    svc._assert_model_alias_on_credential.assert_awaited_once_with(cred_id, "gpt-4--abc")


@pytest.mark.asyncio
async def test_member_total_guardrail_scoped_to_team() -> None:
    """成员总量护栏（user，无凭据）应带 tenant 维度，实现按团队隔离。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="user",
        user_id=user_id,
        credential_id=None,
        model_name=None,
        period="monthly",
        limit_usd=Decimal("200"),
    )

    kind, target_id, budget_tenant, period, _anchor = await svc._resolve_platform_target(
        cmd, tenant_id=tenant_id, is_platform_admin=False
    )

    assert (kind, target_id, budget_tenant, period) == ("user", user_id, tenant_id, "monthly")


@pytest.mark.asyncio
async def test_credential_on_tenant_target_rejected_before_db() -> None:
    svc = _writes()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="tenant",
        credential_id=uuid.uuid4(),
        period="monthly",
        limit_usd=Decimal("10"),
    )

    with pytest.raises(ValidationError):
        await svc._resolve_platform_target(
            cmd, tenant_id=uuid.uuid4(), is_platform_admin=False
        )

    svc._assert_credential_in_team.assert_not_awaited()


@pytest.mark.asyncio
async def test_credential_without_model_skips_alias_assert() -> None:
    svc = _writes()
    tenant_id = uuid.uuid4()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="user",
        user_id=uuid.uuid4(),
        credential_id=uuid.uuid4(),
        model_name=None,
        period="monthly",
        limit_usd=Decimal("20"),
    )

    await svc._resolve_platform_target(cmd, tenant_id=tenant_id, is_platform_admin=False)

    svc._assert_credential_in_team.assert_awaited_once()
    svc._assert_model_alias_on_credential.assert_not_awaited()


@pytest.mark.asyncio
async def test_self_service_owned_credential_uses_ownership_assert() -> None:
    """成员自助：用凭据归属断言替代团队管理员断言。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="user",
        user_id=user_id,
        credential_id=cred_id,
        model_name="gpt-4--abc",
        period="monthly",
        limit_usd=Decimal("30"),
    )

    kind, target_id, budget_tenant, period, _anchor = await svc._resolve_platform_target(
        cmd,
        tenant_id=tenant_id,
        is_platform_admin=False,
        actor_user_id=user_id,
        member_self_service=True,
    )

    assert (kind, target_id, budget_tenant, period) == ("user", user_id, None, "monthly")
    svc._assert_credential_owned_by_actor.assert_awaited_once_with(
        cred_id, actor_user_id=user_id, tenant_id=tenant_id
    )
    svc._assert_model_alias_on_credential.assert_awaited_once_with(cred_id, "gpt-4--abc")
    # 自助模式不走团队管理员断言。
    svc._assert_budget_target_in_team.assert_not_awaited()
    svc._assert_credential_in_team.assert_not_awaited()


@pytest.mark.asyncio
async def test_self_service_rejects_other_user_target() -> None:
    svc = _writes()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="user",
        user_id=uuid.uuid4(),  # 非本人
        credential_id=uuid.uuid4(),
        period="monthly",
        limit_usd=Decimal("10"),
    )

    with pytest.raises(ValidationError):
        await svc._resolve_platform_target(
            cmd,
            tenant_id=uuid.uuid4(),
            is_platform_admin=False,
            actor_user_id=uuid.uuid4(),
            member_self_service=True,
        )

    svc._assert_credential_owned_by_actor.assert_not_awaited()


@pytest.mark.asyncio
async def test_self_service_requires_credential() -> None:
    svc = _writes()
    user_id = uuid.uuid4()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="user",
        user_id=user_id,
        credential_id=None,  # 自助必须指定本人凭据
        period="monthly",
        limit_usd=Decimal("10"),
    )

    with pytest.raises(ValidationError):
        await svc._resolve_platform_target(
            cmd,
            tenant_id=uuid.uuid4(),
            is_platform_admin=False,
            actor_user_id=user_id,
            member_self_service=True,
        )

    svc._assert_credential_owned_by_actor.assert_not_awaited()


@pytest.mark.asyncio
async def test_self_service_rejects_non_user_kind() -> None:
    svc = _writes()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="tenant",
        credential_id=uuid.uuid4(),
        period="monthly",
        limit_usd=Decimal("10"),
    )

    with pytest.raises(ValidationError):
        await svc._resolve_platform_target(
            cmd,
            tenant_id=uuid.uuid4(),
            is_platform_admin=False,
            actor_user_id=uuid.uuid4(),
            member_self_service=True,
        )


@pytest.mark.asyncio
async def test_self_service_batch_rejects_downstream_layer() -> None:
    """成员自助批量：downstream 层命令记为失败而非执行。"""
    svc = _writes()
    user_id = uuid.uuid4()
    cmd = QuotaRuleUpsertCommand(
        layer="downstream",
        access_kind="vkey",
        access_id=uuid.uuid4(),
        limit_usd=Decimal("10"),
    )

    result = await svc.batch_upsert_self_quota_rules(
        [cmd], tenant_id=uuid.uuid4(), actor_user_id=user_id
    )

    assert result.succeeded == []
    assert len(result.failed) == 1
    assert result.failed[0].index == 0


@pytest.mark.asyncio
async def test_admin_batch_with_actor_user_id_allows_tenant_target() -> None:
    """管理员 batch 传 actor_user_id 时 platform tenant 配额仍走团队管理员校验链。"""
    svc = _writes()
    tenant_id = uuid.uuid4()
    actor_user_id = uuid.uuid4()
    cmd = QuotaRuleUpsertCommand(
        layer="platform",
        target_kind="tenant",
        period="daily",
        limit_usd=Decimal("25"),
    )

    kind, target_id, budget_tenant, period, _anchor = await svc._resolve_platform_target(
        cmd,
        tenant_id=tenant_id,
        is_platform_admin=False,
        actor_user_id=actor_user_id,
        member_self_service=False,
    )

    assert (kind, target_id, budget_tenant, period) == ("tenant", tenant_id, None, "daily")
    svc._assert_budget_target_in_team.assert_awaited_once()
    svc._assert_credential_owned_by_actor.assert_not_awaited()
