"""audio_speech 成本结算：不再硬编码零成本。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.proxy_response_adapter import adapt_binary_response
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal


def _vkey(team_id: uuid.UUID) -> VirtualKeyPrincipal:
    return VirtualKeyPrincipal(
        vkey_id=uuid.uuid4(),
        vkey_name="test",
        team_id=team_id,
        user_id=uuid.uuid4(),
        allowed_models=(),
        allowed_capabilities=(),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        is_system=False,
    )


class _NoopBudget:
    async def check_rate_limit(self, **_kwargs: object) -> None:
        return None

    async def check_budget(self, **_kwargs: object) -> Any:
        from domains.gateway.application.budget_service import BudgetCheckResult

        return BudgetCheckResult(allowed=True)

    async def reserve(self, **_kwargs: object) -> None:
        return None

    async def release(self, **_kwargs: object) -> None:
        return None

    async def commit(self, **_kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_audio_speech_settles_per_request_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settled: dict[str, Decimal] = {}

    def capture_settle(
        _ctx: ProxyContext,
        _budget: object,
        *,
        tokens: int,
        cost: Decimal,
        requests: int,
        entitlement_guard: object | None = None,
        request_id: str | None = None,
    ) -> None:
        _ = tokens, requests, entitlement_guard, request_id
        settled["cost"] = cost

    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter.schedule_settle_usage",
        capture_settle,
    )

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.AUDIO_SPEECH,
        request_id="req-tts",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    metadata = {"gateway_pricing_upstream": {"per_request_usd": 0.012}}

    result = adapt_binary_response(
        b"audio",
        ctx,
        _NoopBudget(),
        metadata=metadata,
        upstream_custom={"per_request_usd": 0.012},
    )

    assert result == b"audio"
    assert settled.get("cost") == Decimal("0.012")


@pytest.mark.asyncio
async def test_audio_speech_proxy_uses_adapt_binary(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.AUDIO_SPEECH,
        request_id="req-tts2",
        store_full_messages=False,
        guardrail_enabled=False,
    )

    async def fake_invoke(*_a: object, **_k: object) -> bytes:
        return b"pcm"

    monkeypatch.setattr(use_case, "_invoke_non_chat_with_router_fallback", fake_invoke)
    monkeypatch.setattr(
        use_case,
        "prepare_litellm_kwargs",
        AsyncMock(
            return_value={
                "model": "tts-1",
                "metadata": {"gateway_pricing_upstream": {"per_request_usd": 0.005}},
            }
        ),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())

    adapt_mock = MagicMock(side_effect=lambda data, *_a, **_k: data)
    monkeypatch.setattr(
        "domains.gateway.application.proxy_non_chat_pipeline.adapt_binary_response",
        adapt_mock,
    )

    result = await use_case.audio_speech(ctx, {"model": "tts-1", "input": "hi"})
    assert result == b"pcm"
    adapt_mock.assert_called_once()
