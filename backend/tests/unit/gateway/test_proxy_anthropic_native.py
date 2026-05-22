"""ProxyUseCase.anthropic_messages 原生通道单元测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.proxy_response_adapter import (
    enrich_anthropic_response_cost,
)
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal
from domains.gateway.infrastructure.router_singleton import (
    filter_litellm_params_for_direct_anthropic,
)


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


def test_filter_litellm_params_strips_router_only_keys() -> None:
    dep = {"model": "anthropic/claude", "api_key": "sk-x", "rpm": 10, "tpm": 1000}
    assert filter_litellm_params_for_direct_anthropic(dep) == {
        "model": "anthropic/claude",
        "api_key": "sk-x",
    }


def test_enrich_anthropic_response_cost_injects_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_resolve(
        _source: object,
        *,
        metadata: dict[str, object],
        model: str | None,
    ) -> float:
        _ = metadata, model
        return 0.0012

    monkeypatch.setattr(
        "domains.gateway.application.pricing.pricing_display_cost.resolve_downstream_display_cost_usd",
        fake_resolve,
    )

    data = {
        "type": "message",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }

    class _Resp:
        pass

    enriched = enrich_anthropic_response_cost(
        data,
        source_obj=_Resp(),
        metadata={},
        downstream_custom=None,
        model="claude-test",
    )
    assert enriched.get("response_cost") == pytest.approx(0.0012)


@pytest.mark.asyncio
async def test_anthropic_messages_passes_body_fields_to_router(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_router_anthropic(kwargs: dict[str, Any]) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "id": "msg_abc",
            "type": "message",
            "role": "assistant",
            "model": kwargs.get("model"),
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 5,
                "output_tokens": 3,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 1,
            },
        }

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.CHAT,
        request_id="req-1",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    monkeypatch.setattr(
        use_case.litellm, "should_use_internal_direct_litellm", no_direct
    )
    monkeypatch.setattr(
        use_case.litellm, "router_anthropic_messages", fake_router_anthropic
    )

    async def fake_metadata(
        _ctx: ProxyContext, *, user_kwargs: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        meta: dict[str, Any] = {"gateway_request_id": "req-1"}
        if user_kwargs:
            user_meta = user_kwargs.get("metadata")
            if isinstance(user_meta, dict):
                for key, val in user_meta.items():
                    if not str(key).startswith("gateway_"):
                        meta[key] = val
        return meta

    monkeypatch.setattr(use_case.metadata_builder, "build", fake_metadata)

    async def noop_entitlement(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(use_case.guard, "check_entitlement", noop_entitlement)

    body: dict[str, Any] = {
        "model": "claude-test",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "Hi"}],
        "thinking": {"type": "enabled", "budget_tokens": 1024},
        "top_k": 40,
        "metadata": {"trace_id": "t1"},
    }
    result = await use_case.anthropic_messages(ctx, body)
    assert isinstance(result, dict)
    assert result["usage"]["cache_read_input_tokens"] == 1
    assert captured.get("thinking") == body["thinking"]
    assert captured.get("top_k") == 40
    assert captured["messages"] == body["messages"]
    meta = captured.get("metadata")
    assert isinstance(meta, dict)
    assert meta.get("trace_id") == "t1"
    assert meta.get("gateway_request_id") == "req-1"


@pytest.mark.asyncio
async def test_anthropic_messages_stream_yields_sse_bytes(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_stream() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "message_start", "message": {"id": "msg_s", "role": "assistant"}}
        yield {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "x"},
        }
        yield {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"input_tokens": 2, "output_tokens": 1},
        }
        yield {"type": "message_stop"}

    async def fake_router_anthropic(
        _kwargs: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        return fake_stream()

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.CHAT,
        request_id="req-stream",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    monkeypatch.setattr(
        use_case.litellm, "should_use_internal_direct_litellm", no_direct
    )
    monkeypatch.setattr(
        use_case.litellm, "router_anthropic_messages", fake_router_anthropic
    )

    async def fake_metadata(
        _ctx: ProxyContext, *, user_kwargs: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        _ = user_kwargs
        return {}

    monkeypatch.setattr(use_case.metadata_builder, "build", fake_metadata)

    async def noop_entitlement(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(use_case.guard, "check_entitlement", noop_entitlement)

    stream = await use_case.anthropic_messages(
        ctx,
        {
            "model": "claude-test",
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    assert hasattr(stream, "__aiter__")
    payload = b"".join([chunk async for chunk in stream])
    assert b"message_start" in payload
    assert b"content_block_delta" in payload
    assert b"message_stop" in payload
