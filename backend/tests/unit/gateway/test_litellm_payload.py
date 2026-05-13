"""``domains.gateway.application.litellm_bridge_payload`` 拆分逻辑单测。"""

from __future__ import annotations

from typing import Any

import pytest

from domains.gateway.application.litellm_bridge_payload import (
    split_chat_completion_for_bridge,
    split_embedding_for_bridge,
)


def test_split_chat_missing_model_returns_none() -> None:
    assert (
        split_chat_completion_for_bridge(
            {"messages": [{"role": "user", "content": "hi"}]},
        )
        is None
    )


def test_split_chat_missing_messages_returns_none() -> None:
    assert split_chat_completion_for_bridge({"model": "gpt-4o"}) is None


def test_split_chat_messages_not_list_returns_none() -> None:
    assert (
        split_chat_completion_for_bridge(
            {"model": "gpt-4o", "messages": "not-a-list"},
        )
        is None
    )


def test_split_chat_basic_and_extras() -> None:
    kw: dict[str, Any] = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "x"}],
        "temperature": 0.2,
        "max_tokens": 100,
        "stream": True,
        "tools": [{"type": "function", "function": {"name": "f"}}],
        "tool_choice": "auto",
        "response_format": {"type": "json_object"},
        "api_key": "sk-test",
        "api_base": "https://example.com/v1",
        "extra_headers": {"X-Custom": "1"},
        "metadata": {"k": "v"},
    }
    p = split_chat_completion_for_bridge(kw)
    assert p is not None
    assert p.stream is True
    assert p.model == "gpt-4o"
    assert p.messages == [{"role": "user", "content": "x"}]
    assert p.temperature == pytest.approx(0.2)
    assert p.max_tokens == 100
    assert p.tools is not None and len(p.tools) == 1
    assert p.tool_choice == "auto"
    assert p.response_format == {"type": "json_object"}
    assert p.api_key == "sk-test"
    assert p.api_base == "https://example.com/v1"
    assert p.extras == {"extra_headers": {"X-Custom": "1"}, "metadata": {"k": "v"}}


def test_split_chat_defaults_temperature_and_max_tokens() -> None:
    p = split_chat_completion_for_bridge(
        {"model": "m", "messages": [{"role": "user", "content": "h"}]},
    )
    assert p is not None
    assert p.stream is False
    assert p.temperature == pytest.approx(0.7)
    assert p.max_tokens == 4096


def test_split_embedding_missing_input_returns_none() -> None:
    assert split_embedding_for_bridge({"model": "text-embedding-3-small"}) is None


def test_split_embedding_missing_model_returns_none() -> None:
    assert split_embedding_for_bridge({"input": ["a"]}) is None


def test_split_embedding_basic_and_extras() -> None:
    kw: dict[str, Any] = {
        "model": "text-embedding-3-small",
        "input": ["a", "b"],
        "api_key": "k",
        "api_base": "https://api.openai.com/v1",
        "dimensions": 256,
    }
    p = split_embedding_for_bridge(kw)
    assert p is not None
    assert p.inputs == ["a", "b"]
    assert p.model == "text-embedding-3-small"
    assert p.api_key == "k"
    assert p.api_base == "https://api.openai.com/v1"
    assert p.extras == {"dimensions": 256}
