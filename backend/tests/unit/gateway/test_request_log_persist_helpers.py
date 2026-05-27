"""``gateway_provider_for_persist`` — 从 LiteLLM kwargs 提取 provider。"""

from __future__ import annotations

from domains.gateway.infrastructure.callbacks.request_log_persist_helpers import (
    gateway_provider_for_persist,
)


def test_prefers_metadata_gateway_provider() -> None:
    provider = gateway_provider_for_persist(
        {},
        {"gateway_provider": "anthropic"},
    )
    assert provider == "anthropic"


def test_falls_back_to_model_info_gateway_provider() -> None:
    provider = gateway_provider_for_persist(
        {
            "litellm_params": {
                "model_info": {"gateway_provider": "deepseek"},
            }
        },
        {},
    )
    assert provider == "deepseek"


def test_infers_from_litellm_params_model() -> None:
    provider = gateway_provider_for_persist(
        {"litellm_params": {"model": "volcengine/doubao-pro-32k"}},
        {},
    )
    assert provider == "volcengine"


def test_infers_from_response_model_when_metadata_stripped() -> None:
    provider = gateway_provider_for_persist(
        {"model": "gw/t/00000000-0000-0000-0000-000000000001/my-virtual"},
        {},
        response_model="dashscope/qwen-max",
    )
    assert provider == "dashscope"


def test_infers_from_real_model_hint_without_prefix() -> None:
    provider = gateway_provider_for_persist(
        {},
        {},
        model_hints=("doubao-seedance-2-0-260128",),
    )
    assert provider == "volcengine"


def test_skips_router_encoded_model_hint() -> None:
    provider = gateway_provider_for_persist(
        {},
        {},
        model_hints=("gw/t/00000000-0000-0000-0000-000000000001/my-virtual",),
    )
    assert provider is None
