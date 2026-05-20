"""PII Guardrail LiteLLM hook 行为单测。"""

from __future__ import annotations

import pytest

from domains.gateway.infrastructure.guardrails.pii_guardrail import _build_pii_guardrail_instance


@pytest.mark.asyncio
async def test_pre_call_skips_redaction_when_metadata_disabled():
    guard = _build_pii_guardrail_instance(default_enabled=True)
    data: dict = {
        "messages": [{"role": "user", "content": "联系 13912345678"}],
        "metadata": {"guardrail_enabled": False},
    }
    await guard.async_pre_call_hook(None, None, data, "completion")
    assert "13912345678" in data["messages"][0]["content"]
    assert "pii_redactions" not in data.get("metadata", {})


@pytest.mark.asyncio
async def test_pre_call_redacts_when_metadata_enabled():
    guard = _build_pii_guardrail_instance(default_enabled=True)
    data: dict = {
        "messages": [{"role": "user", "content": "联系 13912345678"}],
        "metadata": {"guardrail_enabled": True},
    }
    await guard.async_pre_call_hook(None, None, data, "completion")
    assert "13912345678" not in data["messages"][0]["content"]
    assert data["metadata"].get("pii_redactions")


@pytest.mark.asyncio
async def test_pre_call_uses_default_enabled_when_metadata_omitted():
    guard = _build_pii_guardrail_instance(default_enabled=False)
    data: dict = {
        "messages": [{"role": "user", "content": "联系 13912345678"}],
        "metadata": {},
    }
    await guard.async_pre_call_hook(None, None, data, "completion")
    assert "13912345678" in data["messages"][0]["content"]
