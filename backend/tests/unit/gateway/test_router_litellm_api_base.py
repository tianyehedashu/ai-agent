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


def test_build_litellm_params_moonshot_coding_plan_injects_user_agent(monkeypatch) -> None:
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
    cred.profile_id = "moonshot.coding_plan"
    cred.extra = {}

    params = _build_litellm_params(
        real_model="kimi-for-coding",
        provider="moonshot",
        credential=cred,
        rpm_limit=None,
        tpm_limit=None,
        tags=None,
    )
    assert params["extra_headers"]["User-Agent"] == "claude-code/1.0"
