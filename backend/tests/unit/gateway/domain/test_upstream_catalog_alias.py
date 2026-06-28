"""上游模型 id → 客户端别名派生。"""

from __future__ import annotations

from domains.gateway.domain.upstream.upstream_catalog_policy import derive_client_facing_model_alias


def test_strip_anthropic_compact_date_suffix() -> None:
    assert derive_client_facing_model_alias("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5"
    assert derive_client_facing_model_alias("claude-opus-4-1-20250805") == "claude-opus-4-1"


def test_strip_openai_dashed_date_suffix() -> None:
    assert derive_client_facing_model_alias("gpt-4o-2024-08-06") == "gpt-4o"
    assert derive_client_facing_model_alias("gpt-4.1-2025-04-14") == "gpt-4.1"


def test_passthrough_short_name() -> None:
    assert derive_client_facing_model_alias("gpt-4o") == "gpt-4o"
    assert derive_client_facing_model_alias("claude-sonnet-4-5") == "claude-sonnet-4-5"


def test_passthrough_when_no_date_suffix() -> None:
    """长得像但不是日期的字符串不应被误伤。"""
    assert derive_client_facing_model_alias("gpt-4o-mini") == "gpt-4o-mini"
    assert derive_client_facing_model_alias("o3-mini") == "o3-mini"
