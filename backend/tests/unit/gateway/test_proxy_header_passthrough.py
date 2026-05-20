"""proxy_header_passthrough 单元测试。"""

from __future__ import annotations

from domains.gateway.application.prompt_cache_middleware import PromptCacheMiddleware
from domains.gateway.domain.http_header_merge import merge_anthropic_beta_values
from domains.gateway.presentation.proxy_header_passthrough import merge_extra_headers_from_request


def test_merge_extra_headers_anthropic_beta_comma_merge() -> None:
    body: dict[str, object] = {
        "extra_headers": {"anthropic-beta": "tools-2024-04-04"},
    }
    merge_extra_headers_from_request(
        body,
        {
            "anthropic-beta": "extended-cache-ttl-2025-04-11",
            "Authorization": "Bearer sk-gw-x",
        },
    )
    extra = body["extra_headers"]
    assert isinstance(extra, dict)
    beta = str(extra.get("anthropic-beta", ""))
    assert "tools-2024-04-04" in beta
    assert "extended-cache-ttl-2025-04-11" in beta
    assert "authorization" not in {k.lower() for k in extra}


def test_prompt_cache_merges_client_anthropic_beta() -> None:
    middleware = PromptCacheMiddleware()
    out = middleware.inbound(
        {"model": "claude-sonnet-4-5", "extra_headers": {"anthropic-beta": "tools-2024-04-04"}},
        model="claude-sonnet-4-5",
        tags=None,
    )
    beta = out["extra_headers"]["anthropic-beta"]
    assert "tools-2024-04-04" in beta
    assert "prompt-caching-2024-07-31" in beta


def test_merge_anthropic_beta_values_dedupes() -> None:
    merged = merge_anthropic_beta_values("a,b", "b,c")
    assert merged == "a,b,c"
