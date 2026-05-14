"""gateway_internal_log_context 单元测试。"""

from __future__ import annotations

import pytest

from bootstrap.config import settings
from domains.gateway.application.gateway_internal_log_context import (
    SESSION_GATEWAY_VERBOSE_KEY,
    resolve_internal_store_full_messages,
)


@pytest.mark.unit
def test_resolve_request_true_requires_allow_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gateway_allow_client_request_verbose_log", False)
    assert (
        resolve_internal_store_full_messages(
            request_explicit=True,
            session_config=None,
        )
        is None
    )
    monkeypatch.setattr(settings, "gateway_allow_client_request_verbose_log", True)
    assert (
        resolve_internal_store_full_messages(
            request_explicit=True,
            session_config=None,
        )
        is True
    )


@pytest.mark.unit
def test_resolve_request_false_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gateway_allow_client_request_verbose_log", False)
    assert (
        resolve_internal_store_full_messages(
            request_explicit=False,
            session_config={SESSION_GATEWAY_VERBOSE_KEY: True},
        )
        is False
    )


@pytest.mark.unit
def test_resolve_session_config_when_request_none() -> None:
    assert (
        resolve_internal_store_full_messages(
            request_explicit=None,
            session_config={SESSION_GATEWAY_VERBOSE_KEY: True},
        )
        is True
    )
    assert (
        resolve_internal_store_full_messages(
            request_explicit=None,
            session_config={SESSION_GATEWAY_VERBOSE_KEY: False},
        )
        is False
    )


@pytest.mark.unit
def test_resolve_session_missing_key_returns_none() -> None:
    assert (
        resolve_internal_store_full_messages(
            request_explicit=None,
            session_config={"other": True},
        )
        is None
    )
