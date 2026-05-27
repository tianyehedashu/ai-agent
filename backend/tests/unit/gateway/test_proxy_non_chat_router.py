"""非 Chat 能力经 Router 调用（speech / rerank / moderation / video）。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.proxy_metadata_builder import PreparedLitellmKwargs
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.application.router_deployment_params import (
    VOLCENGINE_IMAGE_ENDPOINT_PROXY_MESSAGE,
)
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal
from libs.exceptions import ValidationError


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


def _patch_preflight_model_resolution(
    use_case: ProxyUseCase,
    monkeypatch: pytest.MonkeyPatch,
    *,
    record: object | None = None,
) -> None:
    async def _resolve(
        ctx: ProxyContext,
        model: str,
        *,
        match_registered_capability: bool = True,
    ) -> ResolvedModelName:
        rec = record or SimpleNamespace(
            capability=ctx.capability.value,
            provider="openai",
            real_model=model,
            tags={},
        )
        return ResolvedModelName(record=rec, route=None, via_route=None)

    monkeypatch.setattr(use_case.guard, "resolve_and_validate_request_model", _resolve)


def _prepared_litellm_invoke(body: dict[str, Any]) -> tuple[PreparedLitellmKwargs, dict[str, Any]]:
    client_model = str(body.get("model", "")).strip()
    invoke_kwargs = {"model": client_model, "metadata": {}}
    if "prompt" in body:
        invoke_kwargs["prompt"] = body["prompt"]
    prepared = PreparedLitellmKwargs(
        kwargs={"model": client_model, "metadata": {}},
        client_model=client_model,
        resolved=None,
    )
    return prepared, invoke_kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "direct_method", "router_attr", "body"),
    [
        (
            "rerank",
            "direct_rerank",
            "arerank",
            {"model": "cohere-rerank", "query": "q", "documents": ["a"]},
        ),
        (
            "moderation",
            "direct_moderation",
            "amoderation",
            {"model": "text-moderation", "input": "hello"},
        ),
        (
            "image_generation",
            "direct_image_generation",
            "aimage_generation",
            {"model": "dall-e-3", "prompt": "a cat"},
        ),
        (
            "audio_transcription",
            "direct_transcription",
            "atranscription",
            {"model": "whisper-1", "file": "audio.wav"},
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
    _patch_preflight_model_resolution(use_case, monkeypatch)

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    async def block_direct(_kwargs: dict[str, Any]) -> dict[str, Any]:
        nonlocal direct_called
        direct_called = True
        raise AssertionError("direct litellm must not be called when router succeeds")

    monkeypatch.setattr(
        use_case.litellm, "should_use_internal_direct_litellm", no_direct
    )
    monkeypatch.setattr(
        use_case,
        "prepare_litellm_kwargs",
        AsyncMock(return_value={"model": body.get("model", ""), "metadata": {}}),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    monkeypatch.setattr(use_case.litellm, direct_method, block_direct)

    with patch(
        "domains.gateway.application.proxy_litellm_client.ensure_router_deployment",
        new=AsyncMock(return_value=router),
    ):
        handler = getattr(use_case, method_name)
        result = await handler(ctx, body)

    assert result == {"ok": True}
    router_fn.assert_awaited_once()
    assert direct_called is False


@pytest.mark.asyncio
async def test_video_generation_non_volcengine_uses_router(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"model": "video-model", "prompt": "a cat"}
    router_fn = AsyncMock(return_value={"ok": True})
    router = MagicMock(avideo_generation=router_fn)

    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    ctx = _ctx()
    _patch_preflight_model_resolution(use_case, monkeypatch)

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    async def block_direct(_kwargs: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("direct litellm must not be called when router succeeds")

    monkeypatch.setattr(
        use_case.litellm, "should_use_internal_direct_litellm", no_direct
    )
    monkeypatch.setattr(
        use_case,
        "prepare_litellm_invoke",
        AsyncMock(side_effect=lambda _ctx, b, **_kw: _prepared_litellm_invoke(b)),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    monkeypatch.setattr(
        use_case.guard, "assert_request_capability_matches_model", AsyncMock()
    )
    monkeypatch.setattr(use_case.litellm, "direct_video_generation", block_direct)
    volcengine_direct = AsyncMock()
    monkeypatch.setattr(
        use_case.litellm, "volcengine_direct_video_generation", volcengine_direct
    )

    with patch(
        "domains.gateway.application.proxy_litellm_client.ensure_router_deployment",
        new=AsyncMock(return_value=router),
    ):
        result = await use_case.video_generation(ctx, body)

    assert result == {"ok": True}
    router_fn.assert_awaited_once()
    volcengine_direct.assert_not_called()


@pytest.mark.asyncio
async def test_volcengine_image_generation_uses_direct_not_router(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"model": "volcengine/seedream", "prompt": "a cat", "size": "1920x1920"}
    record = SimpleNamespace(
        provider="volcengine",
        real_model="seedream",
    )
    prepared, invoke_kwargs = _prepared_litellm_invoke(body)
    prepared = PreparedLitellmKwargs(
        kwargs=prepared.kwargs,
        client_model=prepared.client_model,
        resolved=ResolvedModelName(record=record, route=None, via_route=None),
    )

    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    ctx = _ctx()
    _patch_preflight_model_resolution(use_case, monkeypatch, record=record)

    monkeypatch.setattr(
        use_case,
        "prepare_litellm_invoke",
        AsyncMock(return_value=(prepared, invoke_kwargs)),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    volcengine_direct = AsyncMock(return_value={"data": [{"b64_json": "abc"}]})
    monkeypatch.setattr(
        use_case.litellm, "volcengine_direct_image_generation", volcengine_direct
    )
    router_image = AsyncMock()
    monkeypatch.setattr(use_case.litellm, "router_image_generation", router_image)
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter.schedule_settle_usage",
        lambda *_a, **_k: None,
    )

    result = await use_case.image_generation(ctx, body)

    assert result == {"data": [{"b64_json": "abc"}]}
    volcengine_direct.assert_awaited_once()
    router_image.assert_not_called()


@pytest.mark.asyncio
async def test_volcengine_image_generation_fails_without_image_endpoint(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"model": "volcengine/seedream", "prompt": "a cat"}
    record = SimpleNamespace(
        provider="volcengine",
        real_model="seedream",
        credential_id=uuid.uuid4(),
        rpm_limit=None,
        tpm_limit=None,
        tags={},
    )
    prepared, invoke_kwargs = _prepared_litellm_invoke(body)
    prepared = PreparedLitellmKwargs(
        kwargs=prepared.kwargs,
        client_model=prepared.client_model,
        resolved=ResolvedModelName(record=record, route=None, via_route=None),
    )

    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    ctx = _ctx()
    ctx.capability = GatewayCapability.IMAGE
    _patch_preflight_model_resolution(use_case, monkeypatch, record=record)

    monkeypatch.setattr(
        use_case,
        "prepare_litellm_invoke",
        AsyncMock(return_value=(prepared, invoke_kwargs)),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    monkeypatch.setattr(
        "domains.gateway.application.proxy_litellm_client.resolve_volcengine_image_deployment",
        AsyncMock(
            side_effect=ValidationError(VOLCENGINE_IMAGE_ENDPOINT_PROXY_MESSAGE),
        ),
    )

    with pytest.raises(ValidationError, match="image_endpoint_id"):
        await use_case.image_generation(ctx, body)


@pytest.mark.asyncio
async def test_volcengine_video_generation_uses_direct_not_router(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"model": "seedance-video", "prompt": "a cat"}
    record = SimpleNamespace(
        provider="volcengine",
        real_model="doubao-seedance-1-0-lite-t2v-250428",
    )
    prepared, invoke_kwargs = _prepared_litellm_invoke(body)
    prepared = PreparedLitellmKwargs(
        kwargs=prepared.kwargs,
        client_model=prepared.client_model,
        resolved=ResolvedModelName(record=record, route=None, via_route=None),
    )

    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    ctx = _ctx()
    _patch_preflight_model_resolution(use_case, monkeypatch, record=record)

    monkeypatch.setattr(
        use_case,
        "prepare_litellm_invoke",
        AsyncMock(return_value=(prepared, invoke_kwargs)),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    monkeypatch.setattr(
        use_case.guard, "assert_request_capability_matches_model", AsyncMock()
    )
    volcengine_direct = AsyncMock(
        return_value={
            "id": "cgt-test",
            "object": "video",
            "status": "queued",
            "model": "doubao-seedance-1-0-lite-t2v-250428",
        }
    )
    monkeypatch.setattr(
        use_case.litellm, "volcengine_direct_video_generation", volcengine_direct
    )
    router_video = AsyncMock()
    monkeypatch.setattr(use_case.litellm, "router_video_generation", router_video)

    result = await use_case.video_generation(ctx, body)

    assert result["id"] == "cgt-test"
    volcengine_direct.assert_awaited_once()
    router_video.assert_not_called()


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
    _patch_preflight_model_resolution(use_case, monkeypatch)

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    monkeypatch.setattr(
        use_case.litellm, "should_use_internal_direct_litellm", no_direct
    )
    monkeypatch.setattr(
        use_case,
        "prepare_litellm_kwargs",
        AsyncMock(return_value={"model": "tts-1", "input": "hi", "metadata": {}}),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())
    monkeypatch.setattr(
        "domains.gateway.application.proxy_response_adapter.schedule_settle_usage",
        lambda *_a, **_k: None,
    )

    with patch(
        "domains.gateway.application.proxy_litellm_client.ensure_router_deployment",
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
    _patch_preflight_model_resolution(use_case, monkeypatch)

    calls: list[bool] = []

    async def direct_on_second_check(_ctx: ProxyContext, _model: str) -> bool:
        calls.append(True)
        return len(calls) >= 2

    monkeypatch.setattr(
        use_case.litellm, "should_use_internal_direct_litellm", direct_on_second_check
    )
    monkeypatch.setattr(
        use_case,
        "prepare_litellm_kwargs",
        AsyncMock(return_value={"model": "cohere-rerank", "metadata": {}}),
    )
    monkeypatch.setattr(use_case.guard, "check_entitlement", AsyncMock())

    router_fn = AsyncMock(
        side_effect=RuntimeError("No deployments available for cohere-rerank")
    )
    router = MagicMock(arerank=router_fn)
    direct_rerank = AsyncMock(return_value={"fallback": True})
    monkeypatch.setattr(use_case.litellm, "direct_rerank", direct_rerank)

    with patch(
        "domains.gateway.application.proxy_litellm_client.ensure_router_deployment",
        new=AsyncMock(return_value=router),
    ):
        result = await use_case.rerank(
            ctx,
            {"model": "cohere-rerank", "query": "q", "documents": ["a"]},
        )

    assert result == {"fallback": True}
    direct_rerank.assert_awaited_once()
