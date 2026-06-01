"""cost_calculation 单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

from domains.gateway.infrastructure.callbacks.cost_calculation import (
    extract_usage_tokens,
)


def test_extract_usage_tokens_openai_format() -> None:
    response = SimpleNamespace(
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 20},
        }
    )
    inp, out, cached = extract_usage_tokens(response)
    assert inp == 100
    assert out == 50
    assert cached == 20


def test_extract_usage_tokens_anthropic_format() -> None:
    # extract_usage_tokens 主要识别 OpenAI 统一后的 prompt_tokens / completion_tokens，
    # 但本次修复确保 cache_read_input_tokens（Anthropic 缓存格式）能被正确提取为 cached_tokens。
    response = SimpleNamespace(
        usage={
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 2000,
        }
    )
    _inp, _out, cached = extract_usage_tokens(response)
    assert cached == 2000


def test_extract_usage_tokens_anthropic_object_usage() -> None:
    usage = SimpleNamespace(
        input_tokens=80,
        output_tokens=40,
        cache_read_input_tokens=1000,
    )
    response = SimpleNamespace(usage=usage)
    _inp, _out, cached = extract_usage_tokens(response)
    assert cached == 1000


def test_extract_usage_tokens_openai_priority_over_anthropic() -> None:
    """OpenAI 格式与 Anthropic 格式同时存在时，以 OpenAI 的 prompt_tokens_details 为准。"""
    response = SimpleNamespace(
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 30},
            "cache_read_input_tokens": 2000,
        }
    )
    inp, out, cached = extract_usage_tokens(response)
    assert cached == 30


def test_extract_usage_tokens_no_cache() -> None:
    response = SimpleNamespace(
        usage={
            "prompt_tokens": 10,
            "completion_tokens": 5,
        }
    )
    inp, out, cached = extract_usage_tokens(response)
    assert inp == 10
    assert out == 5
    assert cached == 0


def test_extract_usage_tokens_none_response() -> None:
    inp, out, cached = extract_usage_tokens(None)
    assert inp == 0
    assert out == 0
    assert cached == 0
