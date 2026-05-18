"""``libs.llm.litellm_model_id`` 单元测试。"""

from __future__ import annotations

import pytest

from libs.llm.litellm_model_id import build_litellm_model_id


@pytest.mark.parametrize(
    ("provider", "model_id", "expected"),
    [
        ("dashscope", "qwen-max", "dashscope/qwen-max"),
        ("dashscope", "dashscope/qwen-max", "dashscope/qwen-max"),
        ("deepseek", "deepseek-chat", "deepseek/deepseek-chat"),
        ("volcengine", "ep-1", "volcengine/ep-1"),
        ("zhipuai", "glm-4", "zai/glm-4"),
        ("zhipuai", "zai/glm-4", "zai/glm-4"),
        ("openai", "gpt-4o-mini", "gpt-4o-mini"),
        ("openai", "azure/foo", "azure/foo"),
    ],
)
def test_build_litellm_model_id(provider: str, model_id: str, expected: str) -> None:
    assert build_litellm_model_id(provider, model_id) == expected
