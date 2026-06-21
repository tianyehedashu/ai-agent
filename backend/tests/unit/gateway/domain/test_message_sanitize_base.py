"""message_sanitize_base 单元测试。"""

from __future__ import annotations

from typing import Any

from domains.gateway.domain.policies.message_sanitize_base import (
    is_empty_content,
    is_provider,
    sanitize_messages,
)


class TestIsProvider:
    def test_exact_match(self) -> None:
        assert is_provider("moonshot", "moonshot") is True

    def test_case_insensitive(self) -> None:
        assert is_provider("Moonshot", "moonshot") is True
        assert is_provider("moonshot", "MOONSHOT") is True

    def test_whitespace(self) -> None:
        assert is_provider("  moonshot  ", "moonshot") is True

    def test_mismatch(self) -> None:
        assert is_provider("openai", "moonshot") is False

    def test_none(self) -> None:
        assert is_provider(None, "moonshot") is False

    def test_empty(self) -> None:
        assert is_provider("", "moonshot") is False


class TestIsEmptyContent:
    def test_none(self) -> None:
        assert is_empty_content(None) is True

    def test_empty_string(self) -> None:
        assert is_empty_content("") is True

    def test_whitespace_only(self) -> None:
        assert is_empty_content("   ") is True
        assert is_empty_content("\t\n") is True

    def test_non_empty_string(self) -> None:
        assert is_empty_content("hello") is False
        assert is_empty_content("  hi  ") is False

    def test_non_string(self) -> None:
        assert is_empty_content(0) is False
        assert is_empty_content([]) is False
        assert is_empty_content({}) is False


class TestSanitizeMessages:
    def test_returns_original_when_no_changes(self) -> None:
        messages: list[Any] = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ]
        result = sanitize_messages(
            messages,
            placeholder=" ",
            should_sanitize=lambda msg: msg.get("role") == "user" and msg.get("content") == "",
        )
        assert result is messages

    def test_returns_new_list_when_changes_needed(self) -> None:
        messages: list[Any] = [{"role": "user", "content": ""}]
        result = sanitize_messages(
            messages,
            placeholder=" ",
            should_sanitize=lambda msg: msg.get("role") == "user" and msg.get("content") == "",
        )
        assert result == [{"role": "user", "content": " "}]
        assert result is not messages

    def test_preserves_non_dict_when_not_dropping(self) -> None:
        messages: list[Any] = [{"role": "user", "content": ""}, "extra", 42]
        result = sanitize_messages(
            messages,
            placeholder=" ",
            should_sanitize=lambda msg: msg.get("role") == "user" and msg.get("content") == "",
        )
        assert result[0] == {"role": "user", "content": " "}
        assert result[1] == "extra"
        assert result[2] == 42

    def test_drops_non_dict_when_drop_non_dict_enabled(self) -> None:
        messages: list[Any] = [
            {"role": "user", "content": ""},
            None,
            "invalid",
            {"role": "assistant", "content": "ok"},
        ]
        result = sanitize_messages(
            messages,
            placeholder=" ",
            drop_non_dict=True,
            should_sanitize=lambda msg: msg.get("role") == "user" and msg.get("content") == "",
        )
        assert result == [
            {"role": "user", "content": " "},
            {"role": "assistant", "content": "ok"},
        ]

    def test_does_not_mutate_original(self) -> None:
        original: list[Any] = [{"role": "user", "content": ""}]
        result = sanitize_messages(
            original,
            placeholder=" ",
            should_sanitize=lambda msg: msg.get("role") == "user" and msg.get("content") == "",
        )
        assert result[0]["content"] == " "
        assert original[0]["content"] == ""

    def test_empty_list(self) -> None:
        assert sanitize_messages([], placeholder=" ", should_sanitize=lambda _: False) == []

    def test_predicate_receives_dict_only(self) -> None:
        """谓词只对 dict 元素调用；非 dict 元素由 drop_non_dict 控制。"""
        calls: list[Any] = []

        def capture(msg: dict[str, Any]) -> bool:
            calls.append(msg)
            return False

        messages: list[Any] = [{"role": "user"}, None, 42]
        sanitize_messages(messages, placeholder=" ", should_sanitize=capture)
        assert calls == [{"role": "user"}]

    def test_unhashable_role_dict_preserved(self) -> None:
        """should_sanitize 由调用方控制；基础函数本身不直接访问 role。"""
        messages: list[Any] = [{"role": ["user"], "content": ""}]
        result = sanitize_messages(
            messages,
            placeholder=" ",
            should_sanitize=lambda msg: isinstance(msg.get("role"), str)
            and msg.get("role") == "user",
        )
        assert result is messages
