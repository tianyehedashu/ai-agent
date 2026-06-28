"""NormalizedUsage 域值对象与提取函数单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

from domains.gateway.domain.usage.normalized_usage import (
    NormalizedUsage,
    extract_normalized_usage,
    normalized_usage_from_raw,
)

# ---- NormalizedUsage 属性 ----


def test_input_tokens_normalized_no_cache() -> None:
    u = NormalizedUsage(input_tokens_raw=100, output_tokens=50)
    assert u.input_tokens_normalized == 100


def test_input_tokens_normalized_with_cache() -> None:
    u = NormalizedUsage(input_tokens_raw=100, output_tokens=50, cache_read_tokens=200, cache_creation_tokens=30)
    assert u.input_tokens_normalized == 330  # 100 + 200 + 30


def test_total_tokens() -> None:
    u = NormalizedUsage(input_tokens_raw=100, output_tokens=50, cache_read_tokens=200, cache_creation_tokens=30)
    assert u.total_tokens == 380  # 330 + 50


def test_cached_tokens_for_db() -> None:
    u = NormalizedUsage(cache_read_tokens=200, cache_creation_tokens=30)
    assert u.cached_tokens_for_db == 200


def test_to_db_tuple() -> None:
    u = NormalizedUsage(input_tokens_raw=100, output_tokens=50, cache_read_tokens=200, cache_creation_tokens=30)
    assert u.to_db_tuple() == (330, 50, 200)


def test_to_token_usage() -> None:
    u = NormalizedUsage(input_tokens_raw=100, output_tokens=50, cache_read_tokens=200, cache_creation_tokens=30)
    tu = u.to_token_usage()
    assert tu.input_tokens == 330
    assert tu.output_tokens == 50
    assert tu.cache_read_tokens == 200
    assert tu.cache_creation_tokens == 30
    assert tu.requests == 1


# ---- OpenAI 格式提取 ----


def test_extract_openai_dict_no_cache() -> None:
    response = SimpleNamespace(usage={"prompt_tokens": 100, "completion_tokens": 50})
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 100
    assert u.output_tokens == 50
    assert u.cache_read_tokens == 0
    assert u.cache_creation_tokens == 0
    assert u.input_tokens_normalized == 100
    assert u.total_tokens == 150


def test_extract_openai_dict_with_cache_details_dict() -> None:
    response = SimpleNamespace(
        usage={
            "prompt_tokens": 300,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 200},
        }
    )
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 100  # 300 - 200
    assert u.output_tokens == 50
    assert u.cache_read_tokens == 200
    assert u.input_tokens_normalized == 300  # raw(100) + cached(200)
    assert u.total_tokens == 350


def test_extract_openai_object_with_cache_details_object() -> None:
    details = SimpleNamespace(cached_tokens=150)
    usage_obj = SimpleNamespace(prompt_tokens=250, completion_tokens=80, prompt_tokens_details=details)
    response = SimpleNamespace(usage=usage_obj)
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 100  # 250 - 150
    assert u.cache_read_tokens == 150
    assert u.input_tokens_normalized == 250
    assert u.total_tokens == 330


def test_extract_openai_db_tuple_matches_prompt_tokens() -> None:
    """OpenAI 路径: to_db_tuple() 的 input_tokens 应等于 prompt_tokens。"""
    response = SimpleNamespace(
        usage={
            "prompt_tokens": 500,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 300},
        }
    )
    inp, out, cached = extract_normalized_usage(response).to_db_tuple()
    assert inp == 500  # = prompt_tokens
    assert out == 100
    assert cached == 300


# ---- Anthropic 格式提取 ----


def test_extract_anthropic_dict_no_cache() -> None:
    response = SimpleNamespace(usage={"input_tokens": 100, "output_tokens": 50})
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 100
    assert u.output_tokens == 50
    assert u.cache_read_tokens == 0
    assert u.cache_creation_tokens == 0


def test_extract_anthropic_dict_with_cache_read() -> None:
    response = SimpleNamespace(
        usage={
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 2000,
        }
    )
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 100
    assert u.cache_read_tokens == 2000
    assert u.cache_creation_tokens == 0
    assert u.input_tokens_normalized == 2100
    assert u.total_tokens == 2150


def test_extract_anthropic_dict_with_cache_creation() -> None:
    response = SimpleNamespace(
        usage={
            "input_tokens": 20,
            "output_tokens": 10,
            "cache_read_input_tokens": 500,
            "cache_creation_input_tokens": 100,
        }
    )
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 20
    assert u.cache_read_tokens == 500
    assert u.cache_creation_tokens == 100
    assert u.input_tokens_normalized == 620  # 20 + 500 + 100
    assert u.total_tokens == 630


def test_extract_anthropic_object_format() -> None:
    usage_obj = SimpleNamespace(
        input_tokens=50,
        output_tokens=30,
        cache_read_input_tokens=1000,
        cache_creation_input_tokens=200,
    )
    response = SimpleNamespace(usage=usage_obj)
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 50
    assert u.cache_read_tokens == 1000
    assert u.cache_creation_tokens == 200
    assert u.input_tokens_normalized == 1250


def test_extract_anthropic_db_tuple() -> None:
    """Anthropic 路径: to_db_tuple() 的 input_tokens 应含 cache_read + cache_creation。"""
    response = SimpleNamespace(
        usage={
            "input_tokens": 20,
            "output_tokens": 10,
            "cache_read_input_tokens": 500,
            "cache_creation_input_tokens": 100,
        }
    )
    inp, out, cached = extract_normalized_usage(response).to_db_tuple()
    assert inp == 620  # 20 + 500 + 100
    assert out == 10
    assert cached == 500  # 仅 cache_read


# ---- 边界 ----


def test_extract_none_response() -> None:
    u = extract_normalized_usage(None)
    assert u == NormalizedUsage()
    assert u.total_tokens == 0


def test_extract_none_usage() -> None:
    response = SimpleNamespace(usage=None)
    u = extract_normalized_usage(response)
    assert u == NormalizedUsage()


def test_extract_dict_response() -> None:
    response = {"usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 100
    assert u.output_tokens == 50


def test_extract_empty_usage() -> None:
    response = SimpleNamespace(usage={})
    u = extract_normalized_usage(response)
    assert u == NormalizedUsage()


def test_extract_openai_priority_over_anthropic() -> None:
    """两种格式字段并存时，OpenAI (prompt_tokens > 0) 优先。"""
    response = SimpleNamespace(
        usage={
            "prompt_tokens": 300,
            "completion_tokens": 50,
            "prompt_tokens_details": {"cached_tokens": 100},
            "input_tokens": 999,
            "output_tokens": 888,
            "cache_read_input_tokens": 777,
        }
    )
    u = extract_normalized_usage(response)
    assert u.input_tokens_raw == 200  # 300 - 100
    assert u.output_tokens == 50  # completion_tokens
    assert u.cache_read_tokens == 100


# ---- normalized_usage_from_raw ----


def test_from_raw_anthropic_dict() -> None:
    usage = {"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 200}
    u = normalized_usage_from_raw(usage)
    assert u.input_tokens_raw == 100
    assert u.cache_read_tokens == 200
    assert u.total_tokens == 350


def test_from_raw_openai_dict() -> None:
    usage = {"prompt_tokens": 500, "completion_tokens": 100, "prompt_tokens_details": {"cached_tokens": 300}}
    u = normalized_usage_from_raw(usage)
    assert u.input_tokens_normalized == 500
    assert u.total_tokens == 600


def test_from_raw_none() -> None:
    u = normalized_usage_from_raw(None)
    assert u == NormalizedUsage()


def test_from_raw_with_requests() -> None:
    usage = {"input_tokens": 10, "output_tokens": 5}
    u = normalized_usage_from_raw(usage, requests=3)
    assert u.requests == 3


# ---- SLO fallback ----


def test_slo_fallback_fills_cache() -> None:
    """SLO 提供 cache 数据且原始提取无 cache → 补齐。"""
    original = NormalizedUsage(input_tokens_raw=50, output_tokens=20)
    slo = {"cache_read_input_tokens": 4000, "cache_creation_input_tokens": 500}
    result = original.with_slo_fallback(slo)
    assert result.cache_read_tokens == 4000
    assert result.cache_creation_tokens == 500
    assert result.input_tokens_raw == 50
    assert result.input_tokens_normalized == 4550  # 50 + 4000 + 500


def test_slo_fallback_backfills_input_raw() -> None:
    """SLO 有 cache 且 input_raw == 0 → 全归入 cache。"""
    original = NormalizedUsage(input_tokens_raw=0, output_tokens=30)
    slo = {"cache_read_input_tokens": 4000, "cache_creation_input_tokens": 500}
    result = original.with_slo_fallback(slo)
    assert result.input_tokens_raw == 0
    assert result.cache_read_tokens == 4000
    assert result.cache_creation_tokens == 500
    assert result.input_tokens_normalized == 4500
    assert result.output_tokens == 30


def test_slo_fallback_noop_when_already_present() -> None:
    """已有 cache 值时 SLO 不覆盖。"""
    original = NormalizedUsage(input_tokens_raw=100, cache_read_tokens=200, cache_creation_tokens=50)
    slo = {"cache_read_input_tokens": 9999, "cache_creation_input_tokens": 8888}
    result = original.with_slo_fallback(slo)
    assert result is original  # 返回同一对象


def test_slo_fallback_noop_when_slo_empty() -> None:
    original = NormalizedUsage(input_tokens_raw=100)
    result = original.with_slo_fallback({"cache_read_input_tokens": 0})
    assert result is original


def test_slo_fallback_none_slo() -> None:
    original = NormalizedUsage(input_tokens_raw=100)
    result = original.with_slo_fallback(None)
    assert result is original
