"""展示用 API Key 掩码（不解密集成，仅纯函数）。"""

from __future__ import annotations

import pytest

from domains.gateway.presentation.credential_response import mask_plain_secret_for_display


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
