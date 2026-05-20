"""``domains.gateway.domain.litellm_model_id`` 单元测试。"""

import pytest

from domains.gateway.domain.litellm_model_id import build_litellm_model_id


@pytest.mark.parametrize(
    ("provider", "model_id", "expected"),
    [
        ("openai", "gpt-4o", "gpt-4o"),
        ("deepseek", "deepseek-chat", "deepseek/deepseek-chat"),
        ("zhipuai", "glm-4", "zai/glm-4"),
        ("dashscope", "qwen-max", "dashscope/qwen-max"),
        ("volcengine", "ep-123", "volcengine/ep-123"),
        ("openai", "deepseek/deepseek-chat", "deepseek/deepseek-chat"),
    ],
)
def test_build_litellm_model_id(provider: str, model_id: str, expected: str) -> None:
    assert build_litellm_model_id(provider, model_id) == expected
