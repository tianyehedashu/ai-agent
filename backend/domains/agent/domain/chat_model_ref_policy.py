"""Chat 对话 model_ref 选择策略（纯函数，不含 IO）。"""

from __future__ import annotations

import uuid


def normalize_model_ref(ref: str | None) -> str | None:
    if ref is None:
        return None
    cleaned = str(ref).strip()
    return cleaned or None


def parse_personal_model_uuid(ref: str) -> uuid.UUID | None:
    """ref 为 UUID 字符串时返回 id，否则 None（system 文本 id 或非法）。"""
    try:
        return uuid.UUID(ref)
    except ValueError:
        return None


def accept_system_text_model_ref(ref: str, allowed: frozenset[str]) -> str | None:
    """非 UUID 的 system model id：在可见集内则接受。"""
    cleaned = normalize_model_ref(ref)
    if cleaned is None:
        return None
    if parse_personal_model_uuid(cleaned) is not None:
        return None
    return cleaned if cleaned in allowed else None


def explicit_request_rejection_message(ref: str) -> str:
    return f"模型不在可用列表中: {ref}"


def should_ignore_stale_session_ref(stored: str | None, accepted: str | None) -> bool:
    return normalize_model_ref(stored) is not None and accepted is None


def session_stored_model_ref(session: object) -> str | None:
    cfg = session.config if isinstance(getattr(session, "config", None), dict) else {}
    stored = cfg.get("chat_model_ref")
    return stored if isinstance(stored, str) else None


__all__ = [
    "accept_system_text_model_ref",
    "explicit_request_rejection_message",
    "normalize_model_ref",
    "parse_personal_model_uuid",
    "session_stored_model_ref",
    "should_ignore_stale_session_ref",
]
