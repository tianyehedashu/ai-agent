"""模型连通性测试结果持久化时的文本处理（跨 Agent / Gateway 复用）。"""

from __future__ import annotations

LAST_TEST_REASON_MAX_LEN = 2000


def truncate_last_test_reason(text: object | None) -> str | None:
    """将异常或说明文案截断为可安全落库的长度，并压平换行便于列表展示。"""
    if text is None:
        return None
    s = str(text).strip().replace("\r", " ").replace("\n", " ")
    if not s:
        return None
    if len(s) <= LAST_TEST_REASON_MAX_LEN:
        return s
    return s[: LAST_TEST_REASON_MAX_LEN - 1] + "…"


__all__ = ["LAST_TEST_REASON_MAX_LEN", "truncate_last_test_reason"]
