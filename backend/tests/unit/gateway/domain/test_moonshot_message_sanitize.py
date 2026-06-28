"""moonshot_message_sanitize 单元测试。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.provider.moonshot_message_sanitize import (
    is_moonshot_provider,
    sanitize_messages_for_moonshot,
)


class TestIsMoonshotProvider:
    def test_exact_match(self) -> None:
        assert is_moonshot_provider("moonshot") is True

    def test_case_insensitive(self) -> None:
        assert is_moonshot_provider("Moonshot") is True
        assert is_moonshot_provider("MOONSHOT") is True

    def test_whitespace(self) -> None:
        assert is_moonshot_provider("  moonshot  ") is True

    def test_other_provider(self) -> None:
        assert is_moonshot_provider("openai") is False
        assert is_moonshot_provider("anthropic") is False

    def test_none(self) -> None:
        assert is_moonshot_provider(None) is False

    def test_empty(self) -> None:
        assert is_moonshot_provider("") is False


class TestSanitizeMessagesForMoonshot:
    def test_empty_user_content_becomes_space(self) -> None:
        messages: list[Any] = [
            {"role": "user", "content": ""},
            {"role": "user", "content": "   "},
            {"role": "user", "content": None},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert all(msg["content"] == " " for msg in result)

    def test_empty_assistant_content_becomes_space(self) -> None:
        """覆盖 Moonshot 'role assistant must not be empty' 报错。"""
        messages: list[Any] = [
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": "   "},
            {"role": "assistant", "content": None},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert all(msg["content"] == " " for msg in result)

    def test_assistant_content_null_with_tool_calls_becomes_space(self) -> None:
        """tool_calls 轮次 assistant content:null 也需要非空占位。"""
        messages: list[Any] = [
            {"role": "user", "content": "Read file"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "file content"},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert len(result) == 3
        assert result[1]["content"] == " "
        assert result[1]["tool_calls"] == messages[1]["tool_calls"]
        assert result[2] == messages[2]

    def test_normal_messages_unchanged(self) -> None:
        messages: list[Any] = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert result == messages

    def test_system_empty_content_unchanged(self) -> None:
        """当前仅处理 user/assistant；system 空 content 保持原样。"""
        messages: list[Any] = [
            {"role": "system", "content": ""},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert result == messages

    def test_tool_message_unchanged(self) -> None:
        messages: list[Any] = [
            {"role": "tool", "tool_call_id": "call_1", "content": "result"},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert result == messages

    def test_non_dict_elements_preserved(self) -> None:
        """与 volcengine 不同，moonshot policy 保留非 dict 元素。"""
        messages: list[Any] = [
            {"role": "user", "content": "Hi"},
            "invalid",
            42,
            {"role": "assistant", "content": "Hello"},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert len(result) == 4
        assert result[1] == "invalid"
        assert result[2] == 42

    def test_empty_list(self) -> None:
        assert sanitize_messages_for_moonshot([]) == []

    def test_does_not_mutate_original(self) -> None:
        original: list[Any] = [
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1"}]},
        ]
        result = sanitize_messages_for_moonshot(original)
        assert result[0]["content"] == " "
        assert original[0]["content"] is None

    def test_returns_original_list_when_no_changes_needed(self) -> None:
        """无清洗需求时直接返回原列表，避免无意义分配。"""
        messages: list[Any] = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert result is messages

    def test_returns_new_list_when_changes_needed(self) -> None:
        messages: list[Any] = [
            {"role": "user", "content": ""},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert result == [{"role": "user", "content": " "}]
        assert result is not messages

    def test_unhashable_role_preserved_without_crash(self) -> None:
        """不可 hash 的 role（如 list）不会触发 TypeError，应原样保留。"""
        messages: list[Any] = [
            {"role": ["user"], "content": ""},
            {"role": {"role": "user"}, "content": None},
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert result is messages
        assert result[0] == {"role": ["user"], "content": ""}
        assert result[1] == {"role": {"role": "user"}, "content": None}

    def test_mixed_empty_and_normal(self) -> None:
        """综合场景：user/assistant 空 content + 正常消息 + 非 dict 元素。"""
        messages: list[Any] = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": ""},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "act", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "done"},
            {"role": "assistant", "content": "   "},
            {"role": "user", "content": "Continue"},
            "extra",
        ]
        result = sanitize_messages_for_moonshot(messages)
        assert len(result) == 7
        assert result[0] == {"role": "system", "content": "System prompt"}
        assert result[1]["content"] == " "
        assert result[2]["content"] == " "
        assert "tool_calls" in result[2]
        assert result[3] == {"role": "tool", "tool_call_id": "call_1", "content": "done"}
        assert result[4]["content"] == " "
        assert result[5] == {"role": "user", "content": "Continue"}
        assert result[6] == "extra"
