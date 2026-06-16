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
from domains.gateway.domain.quota_plan import PlanQuotaSpec, QuotaPlanReservation


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


@pytest.mark.asyncio
async def test_provider_plan_uses_gateway_real_model_for_matching(monkeypatch) -> None:
    """Router deployment 注入 gateway_real_model 时，应用其匹配 ProviderPlan（非 LiteLLM model id）。"""
    cred_id = uuid.uuid4()
    captured: dict[str, object] = {}

    async def _capture(**kwargs: object) -> tuple[None, list[object], list[object]]:
        captured.update(kwargs)
        return None, [], []

    provider_guard = ppg.get_provider_plan_guard()
    provider_guard.check_and_reserve = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

    monkeypatch.setattr(
        budget_mod, "maybe_reserve_user_credential_budget", AsyncMock(return_value=None)
    )

    logger = ppg.build_provider_plan_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {},
        "litellm_params": {
            "model": "anthropic/claude-sonnet-4",
            "model_info": {
                "gateway_credential_id": str(cred_id),
                "gateway_real_model": "claude-sonnet-4",
                "gateway_credential_scope": "user",
            },
        },
    }

    await logger.async_pre_call_hook(None, None, data, "completion")

    assert captured["credential_id"] == cred_id
    assert captured["real_model"] == "claude-sonnet-4"


@pytest.mark.asyncio
async def test_provider_plan_stamps_metadata_for_callback(monkeypatch) -> None:
    cred_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(quota_id=quota_id, label="24h", window_seconds=86400)
    reservation = QuotaPlanReservation(
        plan_id=plan_id,
        spec=spec,
        minute_unix=42,
        reserved_requests=1,
    )

    provider_guard = ppg.get_provider_plan_guard()
    provider_guard.check_and_reserve = AsyncMock(  # type: ignore[method-assign]
        return_value=(plan_id, [spec], [reservation])
    )
    monkeypatch.setattr(
        budget_mod, "maybe_reserve_user_credential_budget", AsyncMock(return_value=None)
    )

    logger = ppg.build_provider_plan_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {"gateway_request_id": "req-stamp"},
        "litellm_params": {
            "metadata": {},
            "model_info": {"gateway_credential_id": str(cred_id), "gateway_real_model": "ep-1"},
        },
    }

    await logger.async_pre_call_hook(None, None, data, "completion")

    top_meta = data["metadata"]
    assert top_meta["gateway_provider_plan_id"] == str(plan_id)
    assert top_meta["user_api_key_auth_metadata"]["gateway_provider_plan_id"] == str(plan_id)
    inner_meta = data["litellm_params"]["metadata"]
    assert inner_meta["gateway_provider_plan_id"] == str(plan_id)
    assert inner_meta["gateway_provider_plan_reservations"][0]["quota_id"] == str(quota_id)
