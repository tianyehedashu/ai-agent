"""非 Chat 能力经 Router 调用（speech / rerank / moderation / video）。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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


def _ctx(team_id: uuid.UUID | None = None) -> ProxyContext:
    tid = team_id or uuid.uuid4()
    return ProxyContext(
        team_id=tid,
        user_id=uuid.uuid4(),
        vkey=_vkey(tid),
        capability=GatewayCapability.RERANK,
        request_id="req-nc",
        store_full_messages=False,
        guardrail_enabled=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "direct_method", "router_attr", "body"),
    [
        (
            "rerank",
            "_direct_rerank",
            "arerank",
            {"model": "cohere-rerank", "query": "q", "documents": ["a"]},
        ),
        (
            "moderation",
            "_direct_moderation",
            "amoderation",
            {"model": "text-moderation", "input": "hello"},
        ),
        (
            "video_generation",
            "_direct_video_generation",
            "avideo_generation",
            {"model": "video-model", "prompt": "a cat"},
        ),
    ],
)
async def test_non_chat_uses_router_not_direct_litellm(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    direct_method: str,
    router_attr: str,
    body: dict[str, Any],
) -> None:
    router_fn = AsyncMock(return_value={"ok": True})
    router = MagicMock(**{router_attr: router_fn})
    direct_called = False

    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    ctx = _ctx()

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    async def block_direct(_kwargs: dict[str, Any]) -> dict[str, Any]:
        nonlocal direct_called
        direct_called = True
        raise AssertionError("direct litellm must not be called when router succeeds")

    monkeypatch.setattr(use_case, "_should_use_internal_direct_litellm", no_direct)
    monkeypatch.setattr(
        use_case,
        "_prepare_litellm_kwargs",
        AsyncMock(return_value={"model": body.get("model", ""), "metadata": {}}),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    monkeypatch.setattr(use_case, direct_method, block_direct)

    with patch(
        "domains.gateway.application.proxy_litellm_client.get_router",
        new=AsyncMock(return_value=router),
    ):
        handler = getattr(use_case, method_name)
        result = await handler(ctx, body)

    assert result == {"ok": True}
    router_fn.assert_awaited_once()
    assert direct_called is False


@pytest.mark.asyncio
async def test_audio_speech_uses_router_aspeech(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router_aspeech = AsyncMock(return_value=b"audio-bytes")
    router = MagicMock(aspeech=router_aspeech)

    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    ctx = _ctx()
    ctx.capability = GatewayCapability.AUDIO_SPEECH

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    monkeypatch.setattr(use_case, "_should_use_internal_direct_litellm", no_direct)
    monkeypatch.setattr(
        use_case,
        "_prepare_litellm_kwargs",
        AsyncMock(return_value={"model": "tts-1", "input": "hi", "metadata": {}}),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    monkeypatch.setattr(
        "domains.gateway.application.proxy_non_chat_pipeline.schedule_settle_usage",
        lambda *_a, **_k: None,
    )

    with patch(
        "domains.gateway.application.proxy_litellm_client.get_router",
        new=AsyncMock(return_value=router),
    ):
        result = await use_case.audio_speech(ctx, {"model": "tts-1", "input": "hi"})

    assert result == b"audio-bytes"
    router_aspeech.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_chat_router_miss_falls_back_to_direct(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    ctx = _ctx()

    calls: list[bool] = []

    async def direct_on_second_check(_ctx: ProxyContext, _model: str) -> bool:
        calls.append(True)
        return len(calls) >= 2

    monkeypatch.setattr(use_case, "_should_use_internal_direct_litellm", direct_on_second_check)
    monkeypatch.setattr(
        use_case,
        "_prepare_litellm_kwargs",
        AsyncMock(return_value={"model": "cohere-rerank", "metadata": {}}),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())

    router_fn = AsyncMock(
        side_effect=RuntimeError("No deployments available for cohere-rerank")
    )
    router = MagicMock(arerank=router_fn)
    direct_rerank = AsyncMock(return_value={"fallback": True})
    monkeypatch.setattr(use_case, "_direct_rerank", direct_rerank)

    with patch(
        "domains.gateway.application.proxy_litellm_client.get_router",
        new=AsyncMock(return_value=router),
    ):
        result = await use_case.rerank(
            ctx,
            {"model": "cohere-rerank", "query": "q", "documents": ["a"]},
        )

    assert result == {"fallback": True}
    direct_rerank.assert_awaited_once()
