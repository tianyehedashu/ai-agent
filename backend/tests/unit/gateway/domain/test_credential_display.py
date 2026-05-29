"""credential_display 纯函数单测。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.credential_display import (
    display_api_base_for_credential,
    mask_plain_secret_for_display,
)


@pytest.mark.parametrize(
    ("plain", "expected"),
    [
        ("", "••••"),
        ("   ", "••••"),
        ("short", "••••"),
        ("12345678", "••••"),
        ("sk-test-very-long-key-abcdefgh", "sk-t…efgh"),
    ],
)
def test_mask_plain_secret_for_display(plain: str, expected: str) -> None:
    assert mask_plain_secret_for_display(plain) == expected


def test_display_api_base_prefers_explicit() -> None:
    assert (
        display_api_base_for_credential(
            provider="deepseek",
            api_base="https://custom.example/v1",
            effective_openai="https://api.deepseek.com/v1",
        )
        == "https://custom.example/v1"
    )


def test_display_api_base_falls_back_to_provider_default() -> None:
    assert (
        display_api_base_for_credential(
            provider="deepseek",
            api_base=None,
            effective_openai="https://api.deepseek.com/v1",
        )
        == "https://api.deepseek.com/v1"
    )


def test_display_api_base_falls_back_to_effective_when_no_default() -> None:
    assert (
        display_api_base_for_credential(
            provider="custom",
            api_base=None,
            effective_openai="https://proxy.example/v1",
        )
        == "https://proxy.example/v1"
    )
