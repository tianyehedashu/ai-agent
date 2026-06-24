"""Router deployment litellm_params api_base 解析。"""

from __future__ import annotations

from unittest.mock import MagicMock

from domains.gateway.infrastructure.router_singleton import _build_litellm_params


def test_build_litellm_params_volcengine_coding_normalizes_api_base(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton.decrypt_value",
        lambda _enc, _key: "sk-test",
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton._get_encryption_key",
        lambda: "key",
    )
    cred = MagicMock()
    cred.id = "cred-1"
    cred.api_key_encrypted = "enc"
    cred.api_base = "https://ark.cn-beijing.volces.com/api/coding"
    cred.profile_id = "volcengine.coding_plan"
    cred.extra = {}

    params = _build_litellm_params(
        real_model="deepseek-v4-flash",
        provider="volcengine",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
    )
    assert params["api_base"] == "https://ark.cn-beijing.volces.com/api/coding/v3"
    assert params["model"] == "deepseek-v4-flash"
    assert params["custom_llm_provider"] == "volcengine"


def test_build_litellm_params_anthropic_native_uses_anthropic_root_and_prefix(
    monkeypatch,
) -> None:
    """upstream_call_shape=anthropic_native → ``model=anthropic/...`` + Anthropic-native 根。"""
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton.decrypt_value",
        lambda _enc, _key: "sk-test",
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton._get_encryption_key",
        lambda: "key",
    )
    cred = MagicMock()
    cred.id = "cred-1"
    cred.api_key_encrypted = "enc"
    cred.api_base = "https://ark.cn-beijing.volces.com/api/coding/v3"
    cred.profile_id = "volcengine.coding_plan"
    cred.extra = {}

    params = _build_litellm_params(
        real_model="claude-sonnet-4-20250514",
        provider="volcengine",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        upstream_call_shape="anthropic_native",
    )
    assert params["model"] == "anthropic/claude-sonnet-4-20250514"
    assert params["api_base"] == "https://ark.cn-beijing.volces.com/api/coding"
    assert params["api_key"] == "sk-test"
    assert "custom_llm_provider" not in params


def test_build_litellm_params_moonshot_default_profile_with_coding_api_base_injects_ua(
    monkeypatch,
) -> None:
    """凭据 profile 为 default 但 api_base 命中 Kimi Code endpoint，仍应注入 Coding Agent UA。"""
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton.decrypt_value",
        lambda _enc, _key: "sk-test",
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton._get_encryption_key",
        lambda: "key",
    )
    cred = MagicMock()
    cred.id = "cred-1"
    cred.api_key_encrypted = "enc"
    cred.api_base = "https://api.kimi.com/coding/v1"
    cred.profile_id = "moonshot.default"
    cred.extra = {}

    params = _build_litellm_params(
        real_model="kimi-for-coding",
        provider="moonshot",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
    )
    assert params["api_base"] == "https://api.kimi.com/coding/v1"
    assert params["extra_headers"]["User-Agent"] == "claude-cli/2.1.161"


def _openai_compat_custom_cred(monkeypatch) -> MagicMock:
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton.decrypt_value",
        lambda _enc, _key: "sk-test",
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton._get_encryption_key",
        lambda: "key",
    )
    cred = MagicMock()
    cred.id = "cred-1"
    cred.api_key_encrypted = "enc"
    cred.api_base = "https://apihub.agnes-ai.com/v1"
    cred.profile_id = None
    cred.extra = {}
    return cred


def test_build_litellm_params_image_openai_compat_uses_openai_handler(monkeypatch) -> None:
    """image 能力经第三方 OpenAI 兼容端点：须用 ``openai/`` 前缀走 OpenAI handler。

    ``aimage_generation`` / Router 忽略 ``custom_llm_provider`` kwarg，裸名会报
    ``LLM Provider NOT provided``。
    """
    cred = _openai_compat_custom_cred(monkeypatch)
    params = _build_litellm_params(
        real_model="agnes-image-2.0-flash",
        provider="openai",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        capability="image",
    )
    assert params["model"] == "openai/agnes-image-2.0-flash"
    assert params["custom_llm_provider"] == "openai"
    assert params["api_base"] == "https://apihub.agnes-ai.com/v1"


def test_build_litellm_params_chat_openai_compat_keeps_custom_openai(monkeypatch) -> None:
    """chat 能力经第三方 OpenAI 兼容端点：仍用裸名 + ``custom_openai``（避免 Responses API）。"""
    cred = _openai_compat_custom_cred(monkeypatch)
    params = _build_litellm_params(
        real_model="agnes-1.5-flash",
        provider="openai",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
        capability="chat",
    )
    assert params["model"] == "agnes-1.5-flash"
    assert params["custom_llm_provider"] == "custom_openai"


def test_build_litellm_params_moonshot_default_profile_and_api_base_no_ua(
    monkeypatch,
) -> None:
    """默认 profile + 默认 api_base + 非 Coding 模型，不应注入 UA。"""
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton.decrypt_value",
        lambda _enc, _key: "sk-test",
    )
    monkeypatch.setattr(
        "domains.gateway.infrastructure.router_singleton._get_encryption_key",
        lambda: "key",
    )
    cred = MagicMock()
    cred.id = "cred-1"
    cred.api_key_encrypted = "enc"
    cred.api_base = "https://api.moonshot.ai/v1"
    cred.profile_id = "moonshot.default"
    cred.extra = {}

    params = _build_litellm_params(
        real_model="moonshot-v1-8k",
        provider="moonshot",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
    )
    assert "User-Agent" not in params.get("extra_headers", {})
