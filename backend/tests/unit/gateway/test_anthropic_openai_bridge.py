"""Anthropic ↔ OpenAI 桥接单元测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from domains.gateway.application.anthropic_openai_bridge import (
    anthropic_messages_request_to_openai_chat,
    openai_chat_completion_response_to_anthropic_message,
    openai_chat_stream_chunks_to_anthropic_sse,
)


def test_anthropic_to_openai_minimal() -> None:
    body: dict[str, Any] = {
        "model": "claude-3-haiku-20240307",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": "Hello"}],
    }
    o = anthropic_messages_request_to_openai_chat(body)
    assert o["model"] == "claude-3-haiku-20240307"
    assert o["max_tokens"] == 100
    assert o["messages"][-1]["role"] == "user"
    assert o["messages"][-1]["content"] == "Hello"


def test_anthropic_system_prepended() -> None:
    body: dict[str, Any] = {
        "model": "m",
        "max_tokens": 10,
        "system": "You are helpful.",
        "messages": [{"role": "user", "content": "Hi"}],
    }
    o = anthropic_messages_request_to_openai_chat(body)
    assert o["messages"][0] == {"role": "system", "content": "You are helpful."}
    assert o["messages"][1]["role"] == "user"


def test_anthropic_requires_max_tokens() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        anthropic_messages_request_to_openai_chat(
            {"model": "m", "messages": [{"role": "user", "content": "x"}]},
        )


def test_openai_to_anthropic_text() -> None:
    openai_resp: dict[str, Any] = {
        "id": "chatcmpl-abc",
        "model": "m",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Hi there"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }
    a = openai_chat_completion_response_to_anthropic_message(openai_resp)
    assert a["type"] == "message"
    assert a["role"] == "assistant"
    assert a["stop_reason"] == "end_turn"
    assert a["content"][0]["type"] == "text"
    assert a["content"][0]["text"] == "Hi there"
    assert a["usage"]["input_tokens"] == 3
    assert a["usage"]["output_tokens"] == 2


@pytest.mark.asyncio
async def test_stream_emits_message_start_and_stop() -> None:
    async def chunks() -> AsyncIterator[dict[str, Any]]:
        yield {
            "choices": [
                {
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None,
                }
            ]
        }
        yield {
            "choices": [
                {
                    "delta": {"content": "ab"},
                    "finish_reason": None,
                }
            ]
        }
        yield {
            "choices": [
                {"delta": {}, "finish_reason": "stop"},
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2},
        }

    out = b"".join(
        [
            p
            async for p in openai_chat_stream_chunks_to_anthropic_sse(
                chunks(),
                model="m",
                message_id="msg_test",
            )
        ]
    )
    assert b"event: message_start" in out
    assert b"event: content_block_delta" in out
    assert b'"text":"ab"' in out
    assert b"event: message_stop" in out


def test_messages_route_on_app() -> None:
    from bootstrap.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/v1/messages" in paths
