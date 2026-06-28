"""provider_inference 单元测试。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.provider.provider_inference import infer_provider_name


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("moonshot/kimi-k2.6", "moonshot"),
        ("moonshot/kimi-for-coding", "moonshot"),
        ("kimi-k2.6", "moonshot"),
        ("kimi-for-coding", "moonshot"),
        ("deepseek/deepseek-chat", "deepseek"),
        ("zai/glm-4", "zhipuai"),
        ("gpt-4o", "openai"),
        ("claude-3-5-sonnet", "anthropic"),
    ],
)
def test_infer_provider_name(model: str, expected: str) -> None:
    assert infer_provider_name(model) == expected
