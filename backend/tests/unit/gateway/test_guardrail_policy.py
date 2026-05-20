"""Gateway PII Guardrail 开关策略单测。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.guardrail_policy import (
    assert_vkey_guardrail_create_allowed,
    effective_guardrail_enabled,
)
from libs.exceptions import ValidationError


def test_effective_guardrail_requires_global_and_vkey():
    assert effective_guardrail_enabled(global_guardrail_enabled=False, vkey_guardrail_enabled=True) is False
    assert effective_guardrail_enabled(global_guardrail_enabled=True, vkey_guardrail_enabled=False) is False
    assert effective_guardrail_enabled(global_guardrail_enabled=True, vkey_guardrail_enabled=True) is True


def test_assert_create_rejects_when_global_off():
    with pytest.raises(ValidationError, match="PII"):
        assert_vkey_guardrail_create_allowed(
            global_guardrail_enabled=False,
            requested_guardrail_enabled=True,
        )


def test_assert_create_allows_when_global_off_and_requested_off():
    assert_vkey_guardrail_create_allowed(
        global_guardrail_enabled=False,
        requested_guardrail_enabled=False,
    )


def test_assert_create_message_mentions_env_var():
    with pytest.raises(ValidationError) as exc:
        assert_vkey_guardrail_create_allowed(
            global_guardrail_enabled=False,
            requested_guardrail_enabled=True,
        )
    assert "GATEWAY_DEFAULT_GUARDRAIL_ENABLED" in str(exc.value)
