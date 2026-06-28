"""ProviderQuotaGuard quota-aware cooldown 单测。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.quota.provider_quota_config_cache import ProviderQuotaConfigRow
import domains.gateway.application.quota.provider_quota_guard as ppg
from domains.gateway.application.quota.provider_quota_guard import ProviderQuotaGuard
from domains.gateway.domain.errors import ProviderPlanExhaustedError
from domains.gateway.domain.proxy.deployment_cooldown_port import DeploymentCooldownPort
from domains.gateway.domain.quota.quota_plan import PlanQuotaSpec, QuotaPlanReservation


class _RecordingCooldown(DeploymentCooldownPort):
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def cooldown_deployment(
        self,
        *,
        deployment_id: str,
        reason: str,
    ) -> None:
        self.calls.append(
            {
                "deployment_id": deployment_id,
                "reason": reason,
            }
        )


def _make_spec(rule_id: uuid.UUID, window_seconds: int = 120) -> PlanQuotaSpec:
    return PlanQuotaSpec(
        quota_id=rule_id,
        label="test",
        window_seconds=window_seconds,
    )


def _make_row(rule_id: uuid.UUID, window_seconds: int = 120) -> ProviderQuotaConfigRow:
    return ProviderQuotaConfigRow(
        rule_id=rule_id,
        label="test",
        window_seconds=window_seconds,
        reset_strategy="rolling",
        limit_usd=Decimal("10"),
        limit_tokens=1000,
        limit_requests=10,
    )


def _make_guard(
    *,
    allowed: bool = True,
    cooldown: DeploymentCooldownPort | None = None,
    window_seconds: int = 120,
) -> tuple[ProviderQuotaGuard, uuid.UUID]:
    rule_id = uuid.uuid4()
    quota_service = AsyncMock()
    if allowed:
        quota_service.check_and_reserve = AsyncMock(
            return_value=MagicMock(
                allowed=True,
                reservations=[
                    QuotaPlanReservation(
                        plan_id=rule_id,
                        spec=_make_spec(rule_id, window_seconds),
                        minute_unix=1,
                        reserved_requests=1,
                    )
                ],
            )
        )
    else:
        spec = _make_spec(rule_id, window_seconds)
        exhausted = MagicMock()
        exhausted.spec = spec
        exhausted.exhausted_reason = "requests"
        quota_service.check_and_reserve = AsyncMock(
            return_value=MagicMock(
                allowed=False,
                exhausted_snapshot=exhausted,
            )
        )
    return ProviderQuotaGuard(quota_service=quota_service, cooldown=cooldown), rule_id


@pytest.fixture(autouse=True)
def _patch_provider_quota_cache(monkeypatch) -> None:
    """避免测试依赖真实 Redis / DB。"""
    rule_id = uuid.uuid4()
    row = _make_row(rule_id)

    async def _fake_get_cached(
        credential_id: uuid.UUID,
        real_model: str | None,
        *,
        loader: object,
    ) -> tuple[ProviderQuotaConfigRow, ...]:
        return (row,)

    monkeypatch.setattr(
        "domains.gateway.application.quota.provider_quota_guard.get_cached_provider_quotas",
        _fake_get_cached,
    )


@pytest.mark.asyncio
async def test_quota_exhausted_triggers_deployment_cooldown() -> None:
    cred_id = uuid.uuid4()
    deployment_id = str(uuid.uuid4())
    cooldown = _RecordingCooldown()
    guard, _rule_id = _make_guard(allowed=False, cooldown=cooldown, window_seconds=120)

    with pytest.raises(ProviderPlanExhaustedError):
        await guard.check_and_reserve(
            credential_id=cred_id,
            real_model="ep-1",
            deployment_id=deployment_id,
        )

    assert len(cooldown.calls) == 1
    assert cooldown.calls[0]["deployment_id"] == deployment_id
    assert "provider_quota_exhausted" in str(cooldown.calls[0]["reason"])


@pytest.mark.asyncio
async def test_quota_exhausted_without_deployment_id_does_not_cooldown() -> None:
    cred_id = uuid.uuid4()
    cooldown = _RecordingCooldown()
    guard, _rule_id = _make_guard(allowed=False, cooldown=cooldown)

    with pytest.raises(ProviderPlanExhaustedError):
        await guard.check_and_reserve(
            credential_id=cred_id,
            real_model="ep-1",
            deployment_id=None,
        )

    assert len(cooldown.calls) == 0


@pytest.mark.asyncio
async def test_quota_exhausted_without_cooldown_port_does_not_fail() -> None:
    cred_id = uuid.uuid4()
    deployment_id = str(uuid.uuid4())
    guard, _rule_id = _make_guard(allowed=False, cooldown=None)

    with pytest.raises(ProviderPlanExhaustedError):
        await guard.check_and_reserve(
            credential_id=cred_id,
            real_model="ep-1",
            deployment_id=deployment_id,
        )


@pytest.mark.asyncio
async def test_quota_allowed_does_not_cooldown() -> None:
    cred_id = uuid.uuid4()
    deployment_id = str(uuid.uuid4())
    cooldown = _RecordingCooldown()
    guard, _rule_id = _make_guard(allowed=True, cooldown=cooldown)

    reserved = await guard.check_and_reserve(
        credential_id=cred_id,
        real_model="ep-1",
        deployment_id=deployment_id,
    )

    assert len(reserved) == 1
    assert len(cooldown.calls) == 0


@pytest.mark.asyncio
async def test_pre_call_hook_extracts_deployment_id(monkeypatch) -> None:
    cred_id = uuid.uuid4()
    deployment_id = str(uuid.uuid4())
    captured: dict[str, object] = {}

    async def _capture(**kwargs: object) -> list[object]:
        captured.update(kwargs)
        return []

    import domains.gateway.application.budget.budget_deployment_check as budget_mod

    monkeypatch.setattr(
        budget_mod,
        "maybe_reserve_user_credential_budget",
        AsyncMock(),
    )
    provider_guard = ppg.get_provider_quota_guard()
    monkeypatch.setattr(provider_guard, "check_and_reserve", AsyncMock(side_effect=_capture))

    logger = ppg.build_provider_quota_pre_call_logger()
    data = {
        "metadata": {},
        "litellm_params": {
            "model_info": {
                "id": deployment_id,
                "gateway_credential_id": str(cred_id),
                "gateway_real_model": "ep-1",
            },
        },
    }

    await logger.async_pre_call_hook(None, None, data, "completion")

    assert captured["credential_id"] == cred_id
    assert captured["real_model"] == "ep-1"
    assert captured["deployment_id"] == deployment_id
