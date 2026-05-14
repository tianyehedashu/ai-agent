"""libs.model_connectivity — 连通性测试原因截断"""

from libs.model_connectivity import LAST_TEST_REASON_MAX_LEN, truncate_last_test_reason


def test_truncate_none_returns_none() -> None:
    assert truncate_last_test_reason(None) is None


def test_truncate_short_unchanged() -> None:
    s = "连接失败: 401"
    assert truncate_last_test_reason(s) == s


def test_truncate_long_inserts_ellipsis() -> None:
    long = "x" * (LAST_TEST_REASON_MAX_LEN + 50)
    out = truncate_last_test_reason(long)
    assert out is not None
    assert len(out) == LAST_TEST_REASON_MAX_LEN
    assert out.endswith("…")


def test_truncate_flattens_newlines() -> None:
    assert truncate_last_test_reason("a\nb\rc") == "a b c"
