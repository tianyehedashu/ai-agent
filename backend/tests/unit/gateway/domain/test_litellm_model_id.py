"""``domains.gateway.domain.litellm_model_id`` 单元测试。"""

import pytest

from domains.gateway.domain.litellm_model_id import (
    build_litellm_model_id,
    normalize_gateway_stored_real_model,
    normalize_stored_real_model_for_credential,
    resolve_litellm_custom_llm_provider,
)


@pytest.mark.parametrize(
    ("provider", "model_id", "expected"),
    [
        ("openai", "gpt-4o", "openai/gpt-4o"),
        ("anthropic", "claude-3-5-sonnet-20241022", "anthropic/claude-3-5-sonnet-20241022"),
        ("deepseek", "deepseek-chat", "deepseek/deepseek-chat"),
        ("zhipuai", "glm-4", "zai/glm-4"),
        ("dashscope", "qwen-max", "dashscope/qwen-max"),
        ("volcengine", "ep-123", "volcengine/ep-123"),
        ("moonshot", "kimi-k2.6", "moonshot/kimi-k2.6"),
        ("openai", "deepseek/deepseek-chat", "deepseek/deepseek-chat"),
    ],
)
def test_build_litellm_model_id(provider: str, model_id: str, expected: str) -> None:
    assert build_litellm_model_id(provider, model_id) == expected


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("zhipuai", "zai"),
        ("openai", "openai"),
        ("anthropic", "anthropic"),
        ("deepseek", "deepseek"),
        ("dashscope", "dashscope"),
        ("volcengine", "volcengine"),
        ("moonshot", "moonshot"),
        # 未知 provider 原样透传
        ("some_unknown_provider", "some_unknown_provider"),
    ],
)
def test_resolve_litellm_custom_llm_provider(provider: str, expected: str) -> None:
    assert resolve_litellm_custom_llm_provider(provider) == expected


@pytest.mark.parametrize(
    ("provider", "api_base", "expected"),
    [
        # OpenAI 官方端点 → openai
        ("openai", "https://api.openai.com/v1", "openai"),
        ("openai", "https://api.openai.com/v1/", "openai"),
        # 无 api_base → 视为官方
        ("openai", None, "openai"),
        # 第三方 OpenAI 兼容端点 → custom_openai
        ("openai", "https://zhenze-huhehaote.cmecloud.cn/api/coding/v1", "custom_openai"),
        ("openai", "https://my-proxy.example.com/v1", "custom_openai"),
        # 非 openai provider 不受 api_base 影响
        ("deepseek", "https://some-proxy.com/v1", "deepseek"),
        ("zhipuai", "https://custom-zhipu.com/v1", "zai"),
    ],
)
def test_resolve_litellm_custom_llm_provider_with_api_base(
    provider: str, api_base: str | None, expected: str
) -> None:
    assert resolve_litellm_custom_llm_provider(provider, api_base=api_base) == expected


@pytest.mark.parametrize(
    ("model_id", "api_base", "expected"),
    [
        ("agnes-1.5-flash", "https://apihub.agnes-ai.com/v1", "agnes-1.5-flash"),
        ("openai/agnes-1.5-flash", "https://apihub.agnes-ai.com/v1", "agnes-1.5-flash"),
        ("gpt-4o", "https://api.openai.com/v1", "openai/gpt-4o"),
        ("gpt-4o", None, "openai/gpt-4o"),
    ],
)
def test_normalize_gateway_stored_real_model_openai_custom_endpoint(
    model_id: str, api_base: str | None, expected: str
) -> None:
    assert (
        normalize_gateway_stored_real_model("openai", model_id, api_base=api_base) == expected
    )


def test_normalize_stored_real_model_for_credential_custom_openai_endpoint() -> None:
    class _Cred:
        api_base = "https://apihub.agnes-ai.com/v1"
        api_bases = None

    assert (
        normalize_stored_real_model_for_credential(
            "openai",
            "openai/agnes-1.5-flash",
            _Cred(),
        )
        == "agnes-1.5-flash"
    )
