"""``dashscope_embedding`` 域策略纯函数。"""

from __future__ import annotations

from domains.gateway.domain.policies.dashscope_embedding import (
    DEFAULT_DASHSCOPE_COMPAT_API_BASE,
    build_dashscope_embedding_request,
    normalize_dashscope_embedding_model,
    should_use_dashscope_direct_embedding,
)


def test_should_use_dashscope_direct_embedding() -> None:
    assert should_use_dashscope_direct_embedding("dashscope") is True
    assert should_use_dashscope_direct_embedding("DashScope") is True
    assert should_use_dashscope_direct_embedding("openai") is False


def test_normalize_strips_provider_prefix() -> None:
    assert normalize_dashscope_embedding_model("dashscope/text-embedding-v3") == "text-embedding-v3"
    assert normalize_dashscope_embedding_model("text-embedding-v3") == "text-embedding-v3"


def test_build_request_uses_compatible_embeddings_url() -> None:
    req = build_dashscope_embedding_request(
        api_key="sk-test",
        api_base="https://example.com/compatible-mode/v1",
        model_id="dashscope/text-embedding-v3",
        input_payload=["hello"],
    )
    assert req.url == "https://example.com/compatible-mode/v1/embeddings"
    assert req.auth_header == "Bearer sk-test"
    assert req.json_body["model"] == "text-embedding-v3"
    assert req.json_body["input"] == ["hello"]


def test_build_request_falls_back_to_default_base() -> None:
    req = build_dashscope_embedding_request(
        api_key="k",
        api_base=None,
        model_id="text-embedding-v3",
        input_payload="ping",
    )
    assert req.url == f"{DEFAULT_DASHSCOPE_COMPAT_API_BASE}/embeddings"
    assert req.json_body["input"] == "ping"
