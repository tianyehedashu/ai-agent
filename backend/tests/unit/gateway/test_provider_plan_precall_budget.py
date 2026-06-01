"""Phase2 成员+凭据预算与 ProviderPlan pre_call hook 共存语义单测。

预算耗尽须 hard fail（BudgetExceededError），不进入 ProviderPlan / Router fallback。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
import uuid

import pytest

import domains.gateway.application.budget_deployment_check as budget_mod
import domains.gateway.application.provider_plan_guard as ppg
from domains.gateway.domain.errors import BudgetExceededError


@pytest.mark.asyncio
async def test_budget_exhausted_short_circuits_before_provider_plan(monkeypatch) -> None:
    provider_guard = ppg.get_provider_plan_guard()
    provider_guard.check_and_reserve = AsyncMock()  # type: ignore[method-assign]

    async def _exhausted(_data: dict[str, Any], **_kw: object) -> None:
        raise BudgetExceededError(scope="user_credential", period="monthly", limit=50.0, used=60.0)

    monkeypatch.setattr(budget_mod, "maybe_reserve_user_credential_budget", _exhausted)

    logger = ppg.build_provider_plan_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {"gateway_user_id": str(uuid.uuid4())},
        "litellm_params": {"model_info": {"gateway_credential_id": str(uuid.uuid4())}},
    }

    with pytest.raises(BudgetExceededError):
        await logger.async_pre_call_hook(None, None, data, "completion")

    provider_guard.check_and_reserve.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_plan_runs_when_budget_allows(monkeypatch) -> None:
    cred_id = uuid.uuid4()
    provider_guard = ppg.get_provider_plan_guard()
    provider_guard.check_and_reserve = AsyncMock(return_value=(None, [], []))  # type: ignore[method-assign]

    monkeypatch.setattr(
        budget_mod, "maybe_reserve_user_credential_budget", AsyncMock(return_value=None)
    )

    logger = ppg.build_provider_plan_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {},
        "litellm_params": {
            "model_info": {"gateway_credential_id": str(cred_id), "model_real": "gpt-4"},
        },
    }

    await logger.async_pre_call_hook(None, None, data, "completion")

    provider_guard.check_and_reserve.assert_awaited_once()
