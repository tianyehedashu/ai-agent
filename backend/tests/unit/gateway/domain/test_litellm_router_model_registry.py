"""LiteLLM Router deployment 价目表键与注册条目。"""

from __future__ import annotations

import sys
from typing import ClassVar

import pytest

from domains.gateway.domain.litellm.litellm_router_model_registry import (
    collect_registry_payload_from_deployments,
    litellm_model_info_lookup_key,
    registry_entry_from_deployment,
)


def test_litellm_model_info_lookup_key_volcengine_prefixed() -> None:
    assert (
        litellm_model_info_lookup_key(
            model="volcengine/doubao-seed-character-260628",
            custom_llm_provider="volcengine",
        )
        == "volcengine/doubao-seed-character-260628"
    )


def test_litellm_model_info_lookup_key_ep_endpoint() -> None:
    assert (
        litellm_model_info_lookup_key(
            model="ep-20260515110319-g7qh5",
            custom_llm_provider="volcengine",
        )
        == "volcengine/ep-20260515110319-g7qh5"
    )


def test_registry_entry_uses_context_window_when_known() -> None:
    built = registry_entry_from_deployment(
        litellm_params={
            "model": "volcengine/doubao-seed-2-1-pro-260628",
            "custom_llm_provider": "volcengine",
            "input_cost_per_token": 1e-7,
            "output_cost_per_token": 2e-7,
        },
        model_info={"max_input_tokens": 256000, "capability": "chat"},
    )
    assert built is not None
    key, entry = built
    assert key == "volcengine/doubao-seed-2-1-pro-260628"
    assert entry["max_input_tokens"] == 256000
    assert entry["max_tokens"] == 256000
    assert entry["mode"] == "chat"
    assert entry["litellm_provider"] == "volcengine"
    assert entry["input_cost_per_token"] == 1e-7


def test_registry_entry_omits_max_input_tokens_when_unknown() -> None:
    """未知上下文窗口时不臆造上限，避免 pre_call 误杀大上下文模型。"""
    built = registry_entry_from_deployment(
        litellm_params={
            "model": "volcengine/doubao-seed-character-260628",
            "custom_llm_provider": "volcengine",
        },
        model_info={"capability": "chat"},
    )
    assert built is not None
    _key, entry = built
    assert "max_input_tokens" not in entry
    assert "max_tokens" not in entry


def test_collect_registry_payload_skips_existing_keys() -> None:
    dep = {
        "litellm_params": {
            "model": "volcengine/doubao-seed-translation-250915",
            "custom_llm_provider": "volcengine",
        },
        "model_info": {},
    }
    payload = collect_registry_payload_from_deployments(
        [dep],
        existing_keys=frozenset({"volcengine/doubao-seed-translation-250915"}),
    )
    assert payload == {}


def test_register_router_deployments_in_litellm_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    from domains.gateway.infrastructure.litellm.litellm_router_model_registry import (
        register_router_deployments_in_litellm_registry,
    )

    captured: dict[str, dict] = {}

    class _FakeLitellm:
        model_cost: ClassVar[dict[str, dict]] = {"gpt-4o": {}}

        @staticmethod
        def register_model(payload: dict[str, dict]) -> None:
            captured.update(payload)

    monkeypatch.setitem(sys.modules, "litellm", _FakeLitellm)

    dep = {
        "litellm_params": {
            "model": "volcengine/doubao-seed-evolving",
            "custom_llm_provider": "volcengine",
        },
        "model_info": {"max_input_tokens": 32000, "capability": "chat"},
    }
    count = register_router_deployments_in_litellm_registry([dep])
    assert count == 1
    assert "volcengine/doubao-seed-evolving" in captured
    assert captured["volcengine/doubao-seed-evolving"]["max_input_tokens"] == 32000
