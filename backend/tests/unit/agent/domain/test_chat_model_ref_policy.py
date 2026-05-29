"""chat_model_ref_policy 纯函数单测。"""

from __future__ import annotations

import uuid

import pytest

from domains.agent.domain.chat_model_ref_policy import (
    accept_system_text_model_ref,
    explicit_request_rejection_message,
    normalize_model_ref,
    parse_personal_model_uuid,
    session_stored_model_ref,
    should_ignore_stale_session_ref,
)


def test_normalize_model_ref() -> None:
    assert normalize_model_ref("  gpt-4  ") == "gpt-4"
    assert normalize_model_ref("") is None
    assert normalize_model_ref(None) is None


def test_accept_system_text_model_ref() -> None:
    allowed = frozenset({"deepseek/deepseek-chat"})
    assert accept_system_text_model_ref("deepseek/deepseek-chat", allowed) == "deepseek/deepseek-chat"
    assert accept_system_text_model_ref("missing", allowed) is None


def test_accept_system_text_model_ref_rejects_uuid_shape() -> None:
    uid = str(uuid.uuid4())
    assert accept_system_text_model_ref(uid, frozenset({uid})) is None


def test_explicit_request_rejection_message() -> None:
    assert explicit_request_rejection_message("bad-model") == "模型不在可用列表中: bad-model"


def test_should_ignore_stale_session_ref() -> None:
    assert should_ignore_stale_session_ref("stale", None) is True
    assert should_ignore_stale_session_ref("stale", "ok") is False
    assert should_ignore_stale_session_ref(None, None) is False


def test_session_stored_model_ref() -> None:
    session = type("S", (), {"config": {"chat_model_ref": "  m1  "}})()
    assert session_stored_model_ref(session) == "  m1  "
    assert session_stored_model_ref(type("S", (), {"config": {}})()) is None
