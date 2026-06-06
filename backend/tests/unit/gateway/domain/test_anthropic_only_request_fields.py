"""Anthropic-only 请求字段策略单测。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.policies.anthropic_only_request_fields import (
    ANTHROPIC_MESSAGES_FIELD_POLICY_NATIVE,
    ANTHROPIC_MESSAGES_FIELD_POLICY_TAG,
    ANTHROPIC_ONLY_REQUEST_FIELDS,
    PRESERVE_ANTHROPIC_FIELDS_TAG,
    find_anthropic_only_fields_present,
    is_anthropic_upstream,
    resolve_fields_to_strip,
    should_strip_for_upstream,
    strip_anthropic_only_fields,
)


@pytest.mark.parametrize(
    "provider",
    ["anthropic", "ANTHROPIC", " Anthropic "],
)
def test_is_anthropic_upstream_true(provider: str) -> None:
    assert is_anthropic_upstream(provider) is True


@pytest.mark.parametrize(
    "provider",
    ["volcengine", "openai", "dashscope", "", None, "   "],
)
def test_is_anthropic_upstream_false(provider: str | None) -> None:
    assert is_anthropic_upstream(provider) is False


@pytest.mark.parametrize(
    "provider,expected",
    [
        ("volcengine", True),
        ("openai", True),
        ("Dashscope", True),
        ("anthropic", False),
        ("ANTHROPIC", False),
        (None, False),
        ("", False),
        ("   ", False),
    ],
)
def test_should_strip_for_upstream(provider: str | None, expected: bool) -> None:
    """已知非 Anthropic provider 才剥离；未知 / Anthropic / 空均不剥离。"""
    assert should_strip_for_upstream(provider) is expected


def test_find_anthropic_only_fields_present_enumerates_clean() -> None:
    kwargs = {
        "model": "x",
        "context_management": {"edits": []},
        "anthropic_version": "2023-06-01",
        "messages": [],
    }
    detected = find_anthropic_only_fields_present(kwargs)
    assert set(detected) == {"context_management", "anthropic_version"}


def test_find_does_not_match_thinking_field() -> None:
    """``thinking`` 由 ``invocation_policy`` 按模型粒度处理，不应被本策略命中。"""
    kwargs = {
        "model": "x",
        "thinking": {"type": "enabled"},
        "enable_thinking": True,
    }
    assert find_anthropic_only_fields_present(kwargs) == []


def test_strip_for_volcengine_removes_known_fields_in_place() -> None:
    kwargs = {
        "model": "glm-4-7-251222",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 64,
        "context_management": {"edits": [{"type": "clear_tool_uses_20250919"}]},
        "anthropic_version": "2023-06-01",
        "anthropic_beta": "context-management-2025-06-27",
        "top_p": 0.9,
    }
    dropped = strip_anthropic_only_fields(kwargs, upstream_provider="volcengine")
    assert set(dropped) == {"context_management", "anthropic_version", "anthropic_beta"}
    for key in dropped:
        assert key not in kwargs
    assert kwargs["model"] == "glm-4-7-251222"
    assert kwargs["top_p"] == 0.9
    assert kwargs["messages"] == [{"role": "user", "content": "hi"}]


def test_strip_output_config_for_openai_compat_upstream() -> None:
    """Claude Code 发送的 output_config 在 OpenAI-compat 上游必须剥离。"""
    kwargs = {
        "model": "glm-5-1",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1024,
        "output_config": {"format": {"type": "json", "schema": {}}},
    }
    dropped = strip_anthropic_only_fields(kwargs, upstream_provider="openai")
    assert dropped == ["output_config"]
    assert "output_config" not in kwargs


def test_strip_preserves_thinking_for_non_anthropic_upstream() -> None:
    """``thinking`` 字段不在本策略清单，由模型粒度 ``thinking_param`` 体系处理。

    例：运营若给 volcengine 的某模型配 ``tags["thinking_param"] = "anthropic_extended"``，
    则其 ``thinking`` 字段必须**留到** ``invocation_policy`` 处再判定。本策略此处放手。
    """
    kwargs = {
        "model": "glm-4-7-251222",
        "thinking": {"type": "enabled", "budget_tokens": 1024},
    }
    dropped = strip_anthropic_only_fields(kwargs, upstream_provider="volcengine")
    assert dropped == []
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 1024}


def test_strip_for_anthropic_keeps_all_fields() -> None:
    kwargs = {
        "model": "claude-opus-4-7",
        "context_management": {"edits": []},
        "anthropic_version": "2023-06-01",
    }
    dropped = strip_anthropic_only_fields(kwargs, upstream_provider="anthropic")
    assert dropped == []
    assert "context_management" in kwargs
    assert "anthropic_version" in kwargs


def test_strip_for_unknown_provider_keeps_all_fields() -> None:
    """provider 未知时不剥离，交由 ``litellm.drop_params`` 兜底。"""
    kwargs = {
        "model": "x",
        "context_management": {"edits": []},
    }
    dropped = strip_anthropic_only_fields(kwargs, upstream_provider=None)
    assert dropped == []
    assert "context_management" in kwargs


def test_strip_when_no_fields_present_returns_empty() -> None:
    kwargs = {"model": "glm-4-7-251222", "messages": []}
    dropped = strip_anthropic_only_fields(kwargs, upstream_provider="volcengine")
    assert dropped == []
    assert kwargs == {"model": "glm-4-7-251222", "messages": []}


def test_anthropic_only_field_list_is_immutable() -> None:
    assert isinstance(ANTHROPIC_ONLY_REQUEST_FIELDS, frozenset)
    for field in (
        "context_management",
        "anthropic_version",
        "anthropic_beta",
        "output_config",
        "container",
        "mcp_servers",
    ):
        assert field in ANTHROPIC_ONLY_REQUEST_FIELDS
    assert "thinking" not in ANTHROPIC_ONLY_REQUEST_FIELDS


def test_resolve_fields_to_strip_native_policy_skips_all() -> None:
    kwargs = {
        "context_management": {"edits": []},
        "anthropic_version": "2023-06-01",
    }
    tags = {ANTHROPIC_MESSAGES_FIELD_POLICY_TAG: ANTHROPIC_MESSAGES_FIELD_POLICY_NATIVE}
    assert (
        resolve_fields_to_strip(
            kwargs,
            upstream_provider="volcengine",
            model_tags=tags,
        )
        == []
    )


def test_resolve_fields_to_strip_preserve_fields_partial() -> None:
    kwargs = {
        "context_management": {"edits": []},
        "anthropic_version": "2023-06-01",
        "anthropic_beta": "beta",
    }
    tags = {PRESERVE_ANTHROPIC_FIELDS_TAG: ["context_management", "unknown_field"]}
    assert resolve_fields_to_strip(
        kwargs,
        upstream_provider="volcengine",
        model_tags=tags,
    ) == ["anthropic_version", "anthropic_beta"]


def test_strip_with_native_policy_keeps_all_fields() -> None:
    kwargs = {
        "context_management": {"edits": []},
        "anthropic_version": "2023-06-01",
    }
    tags = {ANTHROPIC_MESSAGES_FIELD_POLICY_TAG: "NATIVE"}
    dropped = strip_anthropic_only_fields(
        kwargs,
        upstream_provider="openai",
        model_tags=tags,
    )
    assert dropped == []
    assert "context_management" in kwargs
    assert "anthropic_version" in kwargs


def test_strip_with_preserve_fields_only_drops_unlisted() -> None:
    kwargs = {
        "context_management": {"edits": []},
        "anthropic_beta": "beta",
    }
    tags = {PRESERVE_ANTHROPIC_FIELDS_TAG: ["context_management"]}
    dropped = strip_anthropic_only_fields(
        kwargs,
        upstream_provider="volcengine",
        model_tags=tags,
    )
    assert dropped == ["anthropic_beta"]
    assert "context_management" in kwargs
    assert "anthropic_beta" not in kwargs
