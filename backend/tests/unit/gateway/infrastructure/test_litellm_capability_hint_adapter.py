"""LitellmCapabilityHintAdapter 单元测试。"""

from __future__ import annotations

from typing import Any

import pytest

from domains.gateway.infrastructure.litellm.litellm_capability_hint_adapter import (
    LitellmCapabilityHintAdapter,
)


def test_get_model_hints_falls_back_to_semantic_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = LitellmCapabilityHintAdapter()
    calls: list[str] = []

    def _fake_get_model_info(*, model: str) -> dict[str, Any]:
        calls.append(model)
        if model == "moonshot/kimi-k2.6":
            return {"supports_vision": True, "mode": "chat"}
        raise ValueError(f"unmapped: {model}")

    monkeypatch.setattr(
        "litellm.get_model_info",
        _fake_get_model_info,
        raising=False,
    )
    import litellm

    monkeypatch.setattr(litellm, "get_model_info", _fake_get_model_info)

    hints = adapter.get_model_hints(provider="volcengine", real_model="kimi-k2.6")
    assert hints is not None
    assert hints.get("supports_vision") is True
    assert calls == ["volcengine/kimi-k2.6", "moonshot/kimi-k2.6"]


def test_candidate_model_ids_deduplicates_when_semantic_matches_provider() -> None:
    adapter = LitellmCapabilityHintAdapter()
    ids = adapter._candidate_model_ids(provider="moonshot", real_model="kimi-k2.6")
    assert ids == ("moonshot/kimi-k2.6",)
