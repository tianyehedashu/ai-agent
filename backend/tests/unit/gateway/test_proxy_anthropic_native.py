"""ProxyUseCase.anthropic_messages 原生通道单元测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
import logging
from types import SimpleNamespace
from typing import Any
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.proxy_response_adapter import (
    enrich_anthropic_response_cost,
)
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_ANTHROPIC,
    THINKING_PARAM_DEEPSEEK_V4,
    THINKING_PARAM_NONE,
)
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


def _patch_anthropic_preflight(
    use_case: ProxyUseCase,
    monkeypatch: pytest.MonkeyPatch,
    *,
    provider: str = "anthropic",
    real_model: str = "claude-test",
    tags: dict[str, Any] | None = None,
) -> None:
    """Mock 入站 preflight 模型解析，避免集成 DB 依赖。"""
    default_tags: dict[str, Any] = {
        "thinking_param": THINKING_PARAM_ANTHROPIC,
        "supports_reasoning": True,
    }
    record = SimpleNamespace(
        capability="chat",
        provider=provider,
        real_model=real_model,
        tags=tags if tags is not None else default_tags,
        upstream_call_shape=None,
    )

    async def _resolve(
        _ctx: ProxyContext,
        _model: str,
        *,
        match_registered_capability: bool = True,
    ) -> ResolvedModelName:
        _ = match_registered_capability
        return ResolvedModelName(record=record, route=None, via_route=None)

    async def _limits(_ctx: ProxyContext, *, estimate_tokens: int = 0) -> None:
        _ = estimate_tokens
        return None

    async def _budget(_ctx: ProxyContext) -> list[object]:
        return []

    monkeypatch.setattr(use_case.guard, "resolve_and_validate_request_model", _resolve)
    monkeypatch.setattr(use_case.guard, "check_limits", _limits)
    monkeypatch.setattr(use_case.guard, "check_budget", _budget)


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
    _patch_anthropic_preflight(use_case, monkeypatch)

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
    _patch_anthropic_preflight(use_case, monkeypatch)

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


@pytest.mark.asyncio
async def test_anthropic_messages_strips_anthropic_only_fields_for_non_anthropic_upstream(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """volcengine 上游：协议私有 ``context_management`` / ``anthropic_version`` 被剥离并产 warning 日志。"""

    captured: dict[str, Any] = {}

    async def fake_router_anthropic(kwargs: dict[str, Any]) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "id": "msg_strip",
            "type": "message",
            "role": "assistant",
            "model": kwargs.get("model"),
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.CHAT,
        request_id="req-strip",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    _patch_anthropic_preflight(
        use_case,
        monkeypatch,
        provider="volcengine",
        real_model="glm-4-7-251222",
        tags={"thinking_param": THINKING_PARAM_NONE, "supports_reasoning": False},
    )

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    monkeypatch.setattr(use_case.litellm, "should_use_internal_direct_litellm", no_direct)
    monkeypatch.setattr(use_case.litellm, "router_anthropic_messages", fake_router_anthropic)

    async def fake_metadata(
        _ctx: ProxyContext, *, user_kwargs: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        _ = user_kwargs
        return {"gateway_request_id": "req-strip", "gateway_provider": "volcengine"}

    monkeypatch.setattr(use_case.metadata_builder, "build", fake_metadata)

    async def noop_entitlement(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(use_case.guard, "check_entitlement", noop_entitlement)

    body: dict[str, Any] = {
        "model": "glm-4-7-251222",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "Hi"}],
        "context_management": {"edits": [{"type": "clear_tool_uses_20250919"}]},
        "anthropic_version": "2023-06-01",
        "top_p": 0.8,
    }

    with caplog.at_level(logging.WARNING, logger="domains.gateway.application.proxy_chat_entries"):
        result = await use_case.anthropic_messages(ctx, body)

    assert isinstance(result, dict)
    assert "context_management" not in captured
    assert "anthropic_version" not in captured
    assert captured.get("top_p") == 0.8
    assert captured["messages"] == body["messages"]

    strip_logs = [r for r in caplog.records if "stripped Anthropic-only fields" in r.getMessage()]
    assert len(strip_logs) == 1
    extra = strip_logs[0]
    assert getattr(extra, "upstream_provider", None) == "volcengine"
    dropped_fields = getattr(extra, "dropped_fields", None)
    assert isinstance(dropped_fields, list)
    assert set(dropped_fields) == {"context_management", "anthropic_version"}


@pytest.mark.asyncio
async def test_anthropic_messages_keeps_fields_for_anthropic_upstream(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """anthropic 上游：Anthropic-only 字段保留透传。"""

    captured: dict[str, Any] = {}

    async def fake_router_anthropic(kwargs: dict[str, Any]) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "id": "msg_keep",
            "type": "message",
            "role": "assistant",
            "model": kwargs.get("model"),
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.CHAT,
        request_id="req-keep",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    _patch_anthropic_preflight(
        use_case,
        monkeypatch,
        provider="anthropic",
        real_model="claude-opus-4-7",
    )

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    monkeypatch.setattr(use_case.litellm, "should_use_internal_direct_litellm", no_direct)
    monkeypatch.setattr(use_case.litellm, "router_anthropic_messages", fake_router_anthropic)

    async def fake_metadata(
        _ctx: ProxyContext, *, user_kwargs: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        _ = user_kwargs
        return {"gateway_request_id": "req-keep", "gateway_provider": "anthropic"}

    monkeypatch.setattr(use_case.metadata_builder, "build", fake_metadata)

    async def noop_entitlement(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(use_case.guard, "check_entitlement", noop_entitlement)

    body: dict[str, Any] = {
        "model": "claude-opus-4-7",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "Hi"}],
        "context_management": {"edits": [{"type": "clear_tool_uses_20250919"}]},
        "thinking": {"type": "enabled", "budget_tokens": 1024},
    }

    await use_case.anthropic_messages(ctx, body)

    assert captured.get("context_management") == body["context_management"]
    assert captured.get("thinking") == body["thinking"]


@pytest.mark.asyncio
async def test_anthropic_messages_translates_thinking_for_deepseek_v4(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude Code 经 ``/v1/messages`` 调用 DeepSeek V4：顶层 thinking → extra_body.thinking。"""

    captured: dict[str, Any] = {}

    async def fake_router_anthropic(kwargs: dict[str, Any]) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "id": "msg_v4",
            "type": "message",
            "role": "assistant",
            "model": kwargs.get("model"),
            "content": [{"type": "text", "text": "ok"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    team_id = uuid.uuid4()
    ctx = ProxyContext(
        team_id=team_id,
        user_id=uuid.uuid4(),
        vkey=_vkey(team_id),
        capability=GatewayCapability.CHAT,
        request_id="req-v4",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    _patch_anthropic_preflight(
        use_case,
        monkeypatch,
        provider="volcengine",
        real_model="deepseek-v4-pro-260425",
        tags={
            "thinking_param": THINKING_PARAM_DEEPSEEK_V4,
            "supports_reasoning": True,
        },
    )

    async def no_direct(_ctx: ProxyContext, _model: str) -> bool:
        return False

    monkeypatch.setattr(use_case.litellm, "should_use_internal_direct_litellm", no_direct)
    monkeypatch.setattr(use_case.litellm, "router_anthropic_messages", fake_router_anthropic)

    async def fake_metadata(
        _ctx: ProxyContext, *, user_kwargs: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        _ = user_kwargs
        return {"gateway_request_id": "req-v4", "gateway_provider": "volcengine"}

    monkeypatch.setattr(use_case.metadata_builder, "build", fake_metadata)

    async def noop_entitlement(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(use_case.guard, "check_entitlement", noop_entitlement)

    body: dict[str, Any] = {
        "model": "deepseek-v4-pro-260425",
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "Hi"}],
        "thinking": {"type": "enabled", "budget_tokens": 1024},
    }

    await use_case.anthropic_messages(ctx, body)

    assert "thinking" not in captured
    extra_body = captured.get("extra_body")
    assert isinstance(extra_body, dict)
    assert extra_body.get("thinking") == {"type": "enabled"}
