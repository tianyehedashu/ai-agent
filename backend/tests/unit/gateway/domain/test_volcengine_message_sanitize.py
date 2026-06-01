"""volcengine_message_sanitize 单元测试。"""

from __future__ import annotations

from typing import Any

import pytest

from domains.gateway.domain.policies.volcengine_message_sanitize import (
    is_volcengine_provider,
    sanitize_messages_for_volcengine,
)


class TestIsVolcengineProvider:
    def test_exact_match(self) -> None:
        assert is_volcengine_provider("volcengine") is True

    def test_case_insensitive(self) -> None:
        assert is_volcengine_provider("Volcengine") is True
        assert is_volcengine_provider("VOLCENGINE") is True

    def test_whitespace(self) -> None:
        assert is_volcengine_provider("  volcengine  ") is True

    def test_other_provider(self) -> None:
        assert is_volcengine_provider("openai") is False
        assert is_volcengine_provider("anthropic") is False

    def test_none(self) -> None:
        assert is_volcengine_provider(None) is False

    def test_empty(self) -> None:
        assert is_volcengine_provider("") is False


class TestSanitizeMessagesForVolcengine:
    def test_drops_null_elements(self) -> None:
        messages: list[Any] = [
            {"role": "user", "content": "Hi"},
            None,
            {"role": "assistant", "content": "Hello"},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hi"}
        assert result[1] == {"role": "assistant", "content": "Hello"}

    def test_drops_non_dict_elements(self) -> None:
        messages: list[Any] = [
            {"role": "user", "content": "Hi"},
            "invalid",
            42,
            {"role": "assistant", "content": "Hello"},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert len(result) == 2

    def test_assistant_content_null_with_tool_calls_becomes_empty_string(self) -> None:
        """Cursor 多轮 tool_call：assistant content:null + tool_calls → content:"" """
        messages: list[Any] = [
            {"role": "user", "content": "Read file"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "read", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": "file content"},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert len(result) == 3
        assert result[1]["content"] == ""
        assert result[1]["tool_calls"] == messages[1]["tool_calls"]
        assert result[2] == messages[2]

    def test_assistant_content_null_without_tool_calls_becomes_empty_string(self) -> None:
        messages: list[Any] = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": None},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert len(result) == 2
        assert result[1]["content"] == ""

    def test_normal_messages_unchanged(self) -> None:
        messages: list[Any] = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert result == messages

    def test_assistant_with_content_not_touched(self) -> None:
        messages: list[Any] = [
            {"role": "assistant", "content": "Some text"},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert result == messages

    def test_empty_list(self) -> None:
        assert sanitize_messages_for_volcengine([]) == []

    def test_does_not_mutate_original(self) -> None:
        original: list[Any] = [
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]},
        ]
        result = sanitize_messages_for_volcengine(original)
        assert result[0]["content"] == ""
        assert original[0]["content"] is None

    def test_tool_message_preserved(self) -> None:
        messages: list[Any] = [
            {"role": "tool", "tool_call_id": "call_1", "content": "result"},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert result == messages

    def test_mixed_null_and_content_null(self) -> None:
        """综合场景：null 元素 + assistant content:null + 正常消息。"""
        messages: list[Any] = [
            {"role": "system", "content": "System prompt"},
            None,
            {"role": "user", "content": "Do something"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "act", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "call_1", "content": "done"},
            {"role": "assistant", "content": None},
            {"role": "user", "content": "Continue"},
        ]
        result = sanitize_messages_for_volcengine(messages)
        assert len(result) == 6
        assert result[0] == {"role": "system", "content": "System prompt"}
        assert result[1] == {"role": "user", "content": "Do something"}
        assert result[2]["content"] == ""
        assert "tool_calls" in result[2]
        assert result[3] == {"role": "tool", "tool_call_id": "call_1", "content": "done"}
        assert result[4]["content"] == ""
        assert result[5] == {"role": "user", "content": "Continue"}
