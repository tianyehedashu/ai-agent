"""平台「成员+凭据+模型」配额写入校验链单测（_resolve_platform_target）。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.write_modules import (
    GatewayManagementWriteService,
)
from domains.gateway.application.management.write_modules.quota_rule_writes import (
    QuotaRuleUpsertCommand,
)
from libs.exceptions import ValidationError


def _writes() -> GatewayManagementWriteService:
    svc = GatewayManagementWriteService(MagicMock())
    svc._assert_budget_target_in_team = AsyncMock()  # type: ignore[method-assign]
    svc._assert_credential_in_team = AsyncMock()  # type: ignore[method-assign]
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

    kind, target_id, budget_tenant, period = await svc._resolve_platform_target(
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

    kind, target_id, budget_tenant, period = await svc._resolve_platform_target(
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
