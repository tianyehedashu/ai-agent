"""Router 单例：PII Guardrail 回调注册与全局开关联动。"""

from __future__ import annotations

import litellm
import pytest

import domains.gateway.infrastructure.litellm.router_singleton as router_singleton
from domains.gateway.infrastructure.litellm.router_singleton import ensure_gateway_callbacks


@pytest.fixture(autouse=True)
def _reset_pii_singleton() -> None:
    router_singleton._pii_guardrail_instance = None
    litellm.callbacks = []
    litellm.drop_params = False
    yield
    router_singleton._pii_guardrail_instance = None
    litellm.callbacks = []
    litellm.drop_params = False


def test_ensure_gateway_callbacks_enables_litellm_drop_params() -> None:
    ensure_gateway_callbacks()
    assert litellm.drop_params is True


def test_pii_callback_not_registered_when_global_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        router_singleton.settings,
        "gateway_default_guardrail_enabled",
        False,
    )
    ensure_gateway_callbacks()
    assert router_singleton._pii_guardrail_instance is None
    assert router_singleton._pii_guardrail_instance not in (litellm.callbacks or [])


def test_pii_callback_registered_when_global_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        router_singleton.settings,
        "gateway_default_guardrail_enabled",
        True,
    )
    ensure_gateway_callbacks()
    assert router_singleton._pii_guardrail_instance is not None
    assert router_singleton._pii_guardrail_instance in litellm.callbacks
