"""Anthropic ``POST /v1/messages`` 原生通道 HTTP 集成测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
import uuid

from httpx import AsyncClient
import pytest

from bootstrap.main import app
from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.errors import BudgetExceededError, RateLimitExceededError
from domains.gateway.domain.types import VirtualKeyPrincipal
from domains.gateway.presentation.deps import (
    VkeyOrApikeyPrincipal,
    bearer_vkey_or_apikey_auth,
)


def _principal() -> VkeyOrApikeyPrincipal:
    team_id = uuid.uuid4()
    return VkeyOrApikeyPrincipal(
        via="vkey",
        user_id=uuid.uuid4(),
        team_id=team_id,
        vkey=VirtualKeyPrincipal(
            vkey_id=uuid.uuid4(),
            vkey_name="integ",
            team_id=team_id,
            user_id=uuid.uuid4(),
            allowed_models=(),
            allowed_capabilities=(),
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=False,
            is_system=False,
        ),
        platform_api_key_id=None,
        api_key_grant=None,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_messages_returns_native_shape(
    dev_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_anthropic_messages(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        _ = self, ctx
        assert body.get("thinking") is not None
        return {
            "id": "msg_integ",
            "type": "message",
            "role": "assistant",
            "model": body.get("model"),
            "content": [{"type": "text", "text": "pong"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 2,
            },
        }

    monkeypatch.setattr(ProxyUseCase, "anthropic_messages", fake_anthropic_messages)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = _principal
    try:
        r = await dev_client.post(
            "/v1/messages",
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": "claude-test",
                "max_tokens": 64,
                "messages": [{"role": "user", "content": "ping"}],
                "thinking": {"type": "enabled", "budget_tokens": 512},
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "message"
    assert data["usage"]["cache_read_input_tokens"] == 2
    assert data["content"][0]["text"] == "pong"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_messages_stream_sse(
    dev_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_stream() -> AsyncIterator[bytes]:
        yield b"event: message_start\ndata: {\"type\":\"message_start\"}\n\n"
        yield b"event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n"

    async def fake_anthropic_messages(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        _ = self, ctx, body
        return fake_stream()

    monkeypatch.setattr(ProxyUseCase, "anthropic_messages", fake_anthropic_messages)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = _principal
    try:
        r = await dev_client.post(
            "/v1/messages",
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": "claude-test",
                "max_tokens": 32,
                "stream": True,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 200, r.text
    assert "text/event-stream" in (r.headers.get("content-type") or "")
    assert b"message_start" in r.content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_messages_rate_limit_returns_anthropic_shape(
    dev_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_raises(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        _ = self, ctx, body
        raise RateLimitExceededError("vkey", retry_after=42)

    monkeypatch.setattr(ProxyUseCase, "anthropic_messages", fake_raises)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = _principal
    try:
        r = await dev_client.post(
            "/v1/messages",
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": "claude-test",
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 429, r.text
    detail = r.json()["detail"]
    assert detail["error"]["type"] == "rate_limit_error"
    assert r.headers.get("retry-after") == "42"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_messages_budget_exceeded_returns_anthropic_api_error(
    dev_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_raises(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        _ = self, ctx, body
        raise BudgetExceededError("team", "daily", 10.0, 10.0)

    monkeypatch.setattr(ProxyUseCase, "anthropic_messages", fake_raises)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = _principal
    try:
        r = await dev_client.post(
            "/v1/messages",
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": "claude-test",
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 402, r.text
    assert r.json()["detail"]["error"]["type"] == "api_error"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_post_messages_count_tokens_returns_input_tokens(
    dev_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_count(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, int]:
        _ = self, ctx
        assert body.get("model") == "claude-test"
        return {"input_tokens": 42}

    monkeypatch.setattr(ProxyUseCase, "anthropic_count_tokens", fake_count)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = _principal
    try:
        r = await dev_client.post(
            "/v1/messages/count_tokens",
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": "claude-test",
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 200, r.text
    assert r.json() == {"input_tokens": 42}
