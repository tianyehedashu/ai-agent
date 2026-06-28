"""``domains.gateway.application.upstream.litellm_real_model_prefix`` 单元测试。"""

from __future__ import annotations

from domains.gateway.application.upstream.litellm_real_model_prefix import litellm_prefix_violation_message


def test_litellm_prefix_violation_none_when_no_slash() -> None:
    assert litellm_prefix_violation_message("dashscope", "qwen-max") is None


def test_litellm_prefix_violation_dashscope_wrong_prefix() -> None:
    msg = litellm_prefix_violation_message("dashscope", "openai/gpt-4")
    assert msg is not None
    assert "dashscope" in msg
    assert "openai" in msg


def test_litellm_prefix_violation_zhipuai_must_zai() -> None:
    assert litellm_prefix_violation_message("zhipuai", "glm-4/garbage") is not None
    assert litellm_prefix_violation_message("zhipuai", "zai/glm-4") is None


def test_litellm_prefix_violation_openai_not_enforced() -> None:
    assert litellm_prefix_violation_message("openai", "azure/foo") is None
