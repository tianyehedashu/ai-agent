"""Phase2 成员+凭据预算与 ProviderQuota pre_call hook 共存语义单测。

预算耗尽须 hard fail（BudgetExceededError），不进入 ProviderQuota / Router fallback。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
import uuid

import pytest

import domains.gateway.application.budget_deployment_check as budget_mod
import domains.gateway.application.provider_quota_guard as ppg
from domains.gateway.application.provider_quota_guard import ProviderQuotaReservation
from domains.gateway.domain.errors import BudgetExceededError
from domains.gateway.domain.quota_plan import PlanQuotaSpec, QuotaPlanReservation


@pytest.mark.asyncio
async def test_budget_exhausted_short_circuits_before_provider_quota(monkeypatch) -> None:
    provider_guard = ppg.get_provider_quota_guard()
    provider_guard.check_and_reserve = AsyncMock()  # type: ignore[method-assign]

    async def _exhausted(_data: dict[str, Any], **_kw: object) -> None:
        raise BudgetExceededError(scope="user_credential", period="monthly", limit=50.0, used=60.0)

    monkeypatch.setattr(budget_mod, "maybe_reserve_user_credential_budget", _exhausted)

    logger = ppg.build_provider_quota_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {"gateway_user_id": str(uuid.uuid4())},
        "litellm_params": {"model_info": {"gateway_credential_id": str(uuid.uuid4())}},
    }

    with pytest.raises(BudgetExceededError):
        await logger.async_pre_call_hook(None, None, data, "completion")

    provider_guard.check_and_reserve.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_quota_runs_when_budget_allows(monkeypatch) -> None:
    cred_id = uuid.uuid4()
    provider_guard = ppg.get_provider_quota_guard()
    provider_guard.check_and_reserve = AsyncMock(return_value=[])  # type: ignore[method-assign]

    monkeypatch.setattr(
        budget_mod, "maybe_reserve_user_credential_budget", AsyncMock(return_value=None)
    )

    logger = ppg.build_provider_quota_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {},
        "litellm_params": {
            "model": "volcengine/ep-legacy",
            "model_info": {"gateway_credential_id": str(cred_id)},
        },
    }

    await logger.async_pre_call_hook(None, None, data, "completion")

    provider_guard.check_and_reserve.assert_awaited_once()
    assert provider_guard.check_and_reserve.await_args is not None
    assert provider_guard.check_and_reserve.await_args.kwargs["real_model"] is None


@pytest.mark.asyncio
async def test_provider_quota_uses_gateway_real_model_for_matching(monkeypatch) -> None:
    cred_id = uuid.uuid4()
    captured: dict[str, object] = {}

    async def _capture(**kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    provider_guard = ppg.get_provider_quota_guard()
    provider_guard.check_and_reserve = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]

    monkeypatch.setattr(
        budget_mod, "maybe_reserve_user_credential_budget", AsyncMock(return_value=None)
    )

    logger = ppg.build_provider_quota_pre_call_logger()
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
async def test_provider_quota_stamps_metadata_for_callback(monkeypatch) -> None:
    cred_id = uuid.uuid4()
    rule_id = uuid.uuid4()
    spec = PlanQuotaSpec(quota_id=rule_id, label="24h", window_seconds=86400)
    reservation = QuotaPlanReservation(
        plan_id=rule_id,
        spec=spec,
        minute_unix=42,
        reserved_requests=1,
    )

    provider_guard = ppg.get_provider_quota_guard()
    provider_guard.check_and_reserve = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            ProviderQuotaReservation(rule_id=rule_id, spec=spec, reservation=reservation)
        ]
    )
    monkeypatch.setattr(
        budget_mod, "maybe_reserve_user_credential_budget", AsyncMock(return_value=None)
    )

    logger = ppg.build_provider_quota_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {"gateway_request_id": "req-stamp"},
        "litellm_params": {
            "metadata": {},
            "model_info": {"gateway_credential_id": str(cred_id), "gateway_real_model": "ep-1"},
        },
    }

    await logger.async_pre_call_hook(None, None, data, "completion")

    top_meta = data["metadata"]
    assert top_meta["gateway_provider_plan_id"] == str(rule_id)
    assert top_meta["user_api_key_auth_metadata"]["gateway_provider_plan_id"] == str(rule_id)
    inner_meta = data["litellm_params"]["metadata"]
    assert inner_meta["gateway_provider_plan_id"] == str(rule_id)
    assert inner_meta["gateway_provider_quota_reservations"][0]["quota_id"] == str(rule_id)


@pytest.mark.asyncio
async def test_provider_quota_deployment_hook_reads_top_level_model_info(monkeypatch) -> None:
    cred_id = uuid.uuid4()
    captured: dict[str, object] = {}

    async def _capture(**kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    provider_guard = ppg.get_provider_quota_guard()
    provider_guard.check_and_reserve = AsyncMock(side_effect=_capture)  # type: ignore[method-assign]
    monkeypatch.setattr(
        budget_mod, "maybe_reserve_user_credential_budget", AsyncMock(return_value=None)
    )

    logger = ppg.build_provider_quota_pre_call_logger()
    data: dict[str, Any] = {
        "metadata": {"gateway_request_id": "req-router"},
        "model_info": {
            "gateway_credential_id": str(cred_id),
            "gateway_real_model": "ep-20260410150612-9pncb",
        },
        "litellm_params": {"model": "ep-20260410150612-9pncb"},
    }

    await logger.async_pre_call_deployment_hook(data, "acompletion")

    assert captured["credential_id"] == cred_id
    assert captured["real_model"] == "ep-20260410150612-9pncb"
