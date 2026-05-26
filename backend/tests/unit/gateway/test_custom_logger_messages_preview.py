"""custom_logger：prompt messages 提取与 Anthropic content blocks 摘要。"""

from __future__ import annotations

from domains.gateway.infrastructure.callbacks.custom_logger import (
    _build_prompt_redacted,
    _extract_request_messages_from_kwargs,
    _message_content_to_text,
    _serialize_messages_preview,
)


def test_message_content_to_text_plain_string() -> None:
    assert _message_content_to_text("hello") == "hello"


def test_message_content_to_text_anthropic_blocks() -> None:
    content = [{"type": "text", "text": "Explain async"}, {"type": "thinking", "thinking": "hmm"}]
    text = _message_content_to_text(content)
    assert "Explain async" in text
    assert "[thinking]hmm" in text


def test_extract_messages_from_optional_params() -> None:
    msgs = [{"role": "user", "content": "hi"}]
    kwargs = {"optional_params": {"messages": msgs}}
    assert _extract_request_messages_from_kwargs(kwargs) == msgs


def test_extract_messages_prefers_top_level() -> None:
    top = [{"role": "user", "content": "top"}]
    nested = [{"role": "user", "content": "nested"}]
    kwargs = {"messages": top, "optional_params": {"messages": nested}}
    assert _extract_request_messages_from_kwargs(kwargs) == top


def test_serialize_messages_preview_anthropic_content() -> None:
    preview = _serialize_messages_preview(
        [{"role": "user", "content": [{"type": "text", "text": "ping"}]}],
        max_chars=500,
    )
    assert preview is not None
    assert preview["text"] == "user:ping"


def test_build_prompt_redacted_verbose_with_blocks() -> None:
    out = _build_prompt_redacted(
        verbose_log=True,
        kwargs_messages=[
            {"role": "user", "content": [{"type": "text", "text": "hello gateway"}]},
        ],
        prompt_max=200,
        pii_redactions=[],
    )
    assert out is not None
    mp = out.get("messages_preview")
    assert isinstance(mp, dict)
    assert "hello gateway" in mp.get("text", "")


def test_build_prompt_redacted_skips_when_not_verbose() -> None:
    out = _build_prompt_redacted(
        verbose_log=False,
        kwargs_messages=[{"role": "user", "content": "secret"}],
        prompt_max=200,
        pii_redactions=[],
    )
    assert out is None
