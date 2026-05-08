"""Sentry 请求脱敏辅助函数单测。"""

from libs.observability.sentry import _redact_query_string


def test_redact_query_string_masks_sensitive_keys() -> None:
    out = _redact_query_string("token=secret&foo=bar&API_KEY=xyz")
    assert "foo=bar" in out
    assert "secret" not in out
    assert "xyz" not in out


def test_redact_query_string_preserves_unknown_keys() -> None:
    assert _redact_query_string("page=1") == "page=1"
