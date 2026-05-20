"""client_type 推断。"""

from __future__ import annotations

from domains.gateway.domain.client_type import infer_client_type


def test_infer_claude_code() -> None:
    assert infer_client_type("claude-cli/1.0.0") == "claude-code"


def test_infer_cursor() -> None:
    assert infer_client_type("Cursor/0.45.0") == "cursor"


def test_infer_openai_sdk() -> None:
    assert infer_client_type("OpenAI/Python 1.0") == "openai-sdk"


def test_infer_unknown() -> None:
    assert infer_client_type(None) == "unknown"
