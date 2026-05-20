"""PromptCacheMiddleware 单元测试。"""

from domains.gateway.application.prompt_cache_middleware import (
    PromptCacheMiddleware,
    apply_gateway_cache_hit_to_metadata,
    parse_cache_hit_from_usage,
)


def test_inbound_injects_cache_control_on_long_system_message() -> None:
    mw = PromptCacheMiddleware()
    out = mw.inbound(
        {"messages": [{"role": "system", "content": "x" * 5000}], "metadata": {}},
        model="deepseek/deepseek-chat",
        tags={"prompt_cache": True},
    )
    assert out["messages"][0].get("cache_control") == {"type": "ephemeral"}


def test_inbound_injects_anthropic_beta_header() -> None:
    mw = PromptCacheMiddleware()
    out = mw.inbound(
        {"messages": [{"role": "system", "content": "x" * 5000}], "metadata": {}},
        model="claude-3-5-sonnet",
        tags={"prompt_cache": True},
    )
    assert out.get("extra_headers", {}).get("anthropic-beta") == "prompt-caching-2024-07-31"


def test_inbound_skips_when_metadata_disable() -> None:
    mw = PromptCacheMiddleware()
    out = mw.inbound(
        {"messages": [{"role": "system", "content": "x" * 5000}], "metadata": {"gateway_prompt_cache": False}},
        model="claude-3-5-sonnet",
        tags={"prompt_cache": True},
    )
    assert "extra_headers" not in out


def test_parse_cache_hit_from_usage() -> None:
    assert parse_cache_hit_from_usage({"prompt_tokens_details": {"cached_tokens": 10}})
    assert not parse_cache_hit_from_usage({"prompt_tokens": 1})


def test_apply_gateway_cache_hit_to_metadata() -> None:
    meta: dict[str, object] = {}
    apply_gateway_cache_hit_to_metadata(
        meta,
        {"prompt_tokens_details": {"cached_tokens": 5}},
    )
    assert meta.get("gateway_cache_hit") is True
