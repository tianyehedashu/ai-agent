"""upstream_registration_match 纯函数测试。"""

from __future__ import annotations

from domains.gateway.domain.upstream_registration_match import (
    format_already_registered_reason,
    match_registered_names,
)


def test_match_openai_style_id() -> None:
    rows = [("my-gpt4", "gpt-4o-mini")]
    assert match_registered_names("openai", "gpt-4o-mini", rows) == ("my-gpt4",)


def test_match_prefixed_real_model() -> None:
    rows = [("qwen-max", "dashscope/qwen-max")]
    assert match_registered_names("dashscope", "qwen-max", rows) == ("qwen-max",)


def test_no_match() -> None:
    rows = [("other", "gpt-4")]
    assert match_registered_names("openai", "gpt-4o-mini", rows) == ()


def test_format_already_registered_reason_single() -> None:
    assert format_already_registered_reason(("alias-1",)) == "已注册为「alias-1」"
