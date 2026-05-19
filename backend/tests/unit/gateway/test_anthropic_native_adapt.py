"""Anthropic 原生通道适配单元测试。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from domains.gateway.application.anthropic_native_adapt import (
    anthropic_response_to_dict,
    anthropic_stream_chunk_to_bytes,
    anthropic_usage_total_tokens,
    estimate_anthropic_request_tokens,
    extract_usage_from_anthropic_stream_event,
    validate_anthropic_messages_body,
)


def test_validate_requires_max_tokens() -> None:
    with pytest.raises(ValueError, match="max_tokens"):
        validate_anthropic_messages_body(
            {"model": "m", "messages": [{"role": "user", "content": "x"}]},
        )


def test_estimate_tokens_with_blocks() -> None:
    body: dict[str, Any] = {
        "model": "m",
        "max_tokens": 100,
        "system": "sys",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image", "source": {"type": "base64", "data": "x"}},
                ],
            },
        ],
    }
    est = estimate_anthropic_request_tokens(body)
    assert est >= 100


def test_usage_total_tokens() -> None:
    assert anthropic_usage_total_tokens({"input_tokens": 3, "output_tokens": 2}) == 5


def test_stream_chunk_dict_to_sse() -> None:
    chunk = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": "hi"},
    }
    out = anthropic_stream_chunk_to_bytes(chunk)
    assert out is not None
    assert b"event: content_block_delta" in out
    assert b'"text":"hi"' in out


def test_extract_usage_from_message_delta() -> None:
    u = extract_usage_from_anthropic_stream_event(
        {"type": "message_delta", "usage": {"input_tokens": 10, "output_tokens": 4}},
    )
    assert u == {"input_tokens": 10, "output_tokens": 4}


def test_extract_usage_includes_cache_tokens() -> None:
    u = extract_usage_from_anthropic_stream_event(
        {
            "type": "message_delta",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_read_input_tokens": 3,
                "cache_creation_input_tokens": 1,
            },
        },
    )
    assert u == {
        "input_tokens": 10,
        "output_tokens": 4,
        "cache_read_input_tokens": 3,
        "cache_creation_input_tokens": 1,
    }


def test_anthropic_response_to_dict_passthrough() -> None:
    data = anthropic_response_to_dict(
        {
            "type": "message",
            "usage": {
                "input_tokens": 1,
                "output_tokens": 2,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 5,
            },
        },
    )
    assert data["usage"]["cache_read_input_tokens"] == 5


@pytest.mark.asyncio
async def test_iter_sse_from_dict_chunks() -> None:
    from domains.gateway.application.anthropic_native_adapt import iter_anthropic_sse_bytes

    async def chunks() -> AsyncIterator[dict[str, Any]]:
        yield {"type": "message_start", "message": {"id": "msg_x", "role": "assistant"}}
        yield {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": "a"},
        }

    out = b"".join([p async for p in iter_anthropic_sse_bytes(chunks())])
    assert b"event: message_start" in out
    assert b"content_block_delta" in out


def test_messages_route_on_app() -> None:
    from bootstrap.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/v1/messages" in paths
