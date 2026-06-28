"""上游探测 model ID → chat API 名称规范化（纯函数单元测试）。"""

import pytest

from domains.gateway.domain.upstream.upstream_model_name_normalize import (
    normalize_upstream_model_id,
)


@pytest.mark.parametrize(
    ("input_id", "expected"),
    [
        # 已知映射：小写+连字符 → 大写+点号
        ("minimax-m2-5", "MiniMax-M2.5"),
        # 已知映射：小写+点号 → 大写+点号
        ("minimax-m2.5", "MiniMax-M2.5"),
        # 正确大小写直接命中
        ("MiniMax-M2.5", "MiniMax-M2.5"),
        # 未知模型：原样返回
        ("gpt-4o", "gpt-4o"),
        ("claude-3-5-sonnet-20241022", "claude-3-5-sonnet-20241022"),
        ("deepseek-chat", "deepseek-chat"),
        # 边界
        ("", ""),
        ("  ", ""),
        ("  gpt-4o  ", "gpt-4o"),
    ],
)
def test_normalize_upstream_model_id(input_id: str, expected: str) -> None:
    assert normalize_upstream_model_id(input_id) == expected
