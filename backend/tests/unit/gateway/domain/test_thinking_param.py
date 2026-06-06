"""thinking_param 推断单元测试。"""

from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_ANTHROPIC,
    THINKING_PARAM_BUILTIN,
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_DEEPSEEK_V4,
    THINKING_PARAM_NONE,
    enrich_gateway_model_tags,
    infer_thinking_param,
    is_deepseek_v4_model_id,
    is_moonshot_model,
    resolve_thinking_param_from_tags,
)


def test_infer_qwen3_dashscope() -> None:
    assert (
        infer_thinking_param(provider="dashscope", real_model="dashscope/qwen3-32b")
        == THINKING_PARAM_DASHSCOPE
    )


def test_infer_qwq_builtin() -> None:
    assert (
        infer_thinking_param(provider="dashscope", real_model="qwq-32b-preview")
        == THINKING_PARAM_BUILTIN
    )


def test_infer_deepseek_reasoner() -> None:
    assert (
        infer_thinking_param(provider="deepseek", real_model="deepseek/deepseek-reasoner")
        == THINKING_PARAM_BUILTIN
    )


def test_infer_deepseek_v4_pro() -> None:
    assert (
        infer_thinking_param(provider="deepseek", real_model="deepseek/deepseek-v4-pro")
        == THINKING_PARAM_DEEPSEEK_V4
    )


def test_infer_deepseek_v4_flash_volcengine() -> None:
    assert (
        infer_thinking_param(provider="volcengine", real_model="deepseek-v4-flash-260425")
        == THINKING_PARAM_DEEPSEEK_V4
    )


def test_is_deepseek_v4_model_id_alias() -> None:
    assert is_deepseek_v4_model_id("deepseek-v4-pro-260425")
    assert not is_deepseek_v4_model_id("deepseek-chat")


def test_infer_anthropic_extended() -> None:
    assert (
        infer_thinking_param(
            provider="anthropic",
            real_model="claude-opus-4",
            supports_reasoning=True,
        )
        == THINKING_PARAM_ANTHROPIC
    )


def test_infer_none_for_qwen_turbo() -> None:
    assert (
        infer_thinking_param(provider="dashscope", real_model="qwen-turbo") == THINKING_PARAM_NONE
    )


def test_resolve_explicit_tag() -> None:
    assert (
        resolve_thinking_param_from_tags(
            {"thinking_param": "builtin_reasoning"},
            provider="openai",
            real_model="gpt-4",
        )
        == THINKING_PARAM_BUILTIN
    )


def test_resolve_stale_none_overridden_by_v4_real_model() -> None:
    assert (
        resolve_thinking_param_from_tags(
            {"thinking_param": "none"},
            provider="deepseek",
            real_model="deepseek/deepseek-v4-pro",
        )
        == THINKING_PARAM_DEEPSEEK_V4
    )


def test_resolve_locked_none_respected_for_v4() -> None:
    from domains.gateway.domain.thinking_param import THINKING_PARAM_LOCKED_TAG

    assert (
        resolve_thinking_param_from_tags(
            {
                "thinking_param": "none",
                THINKING_PARAM_LOCKED_TAG: True,
            },
            provider="deepseek",
            real_model="deepseek/deepseek-v4-pro",
        )
        == THINKING_PARAM_NONE
    )


def test_enrich_locked_none_persists_for_v4() -> None:
    from domains.gateway.domain.thinking_param import THINKING_PARAM_LOCKED_TAG

    out = enrich_gateway_model_tags(
        {"thinking_param": "none", THINKING_PARAM_LOCKED_TAG: True},
        provider="deepseek",
        real_model="deepseek/deepseek-v4-pro",
    )
    assert out["thinking_param"] == THINKING_PARAM_NONE
    assert out["supports_reasoning"] is False


def test_resolve_reasoning_content_flag() -> None:
    assert (
        resolve_thinking_param_from_tags(
            {"supports_reasoning_content": True},
            provider="dashscope",
            real_model="qwen3-32b",
        )
        == THINKING_PARAM_DASHSCOPE
    )


def test_enrich_gateway_model_tags_persists_qwen3() -> None:
    out = enrich_gateway_model_tags(
        {},
        provider="dashscope",
        real_model="dashscope/qwen3-32b",
    )
    assert out["thinking_param"] == THINKING_PARAM_DASHSCOPE
    assert out["supports_reasoning"] is True


def test_enrich_gateway_model_tags_persists_deepseek_v4() -> None:
    out = enrich_gateway_model_tags(
        {},
        provider="deepseek",
        real_model="deepseek/deepseek-v4-pro",
    )
    assert out["thinking_param"] == THINKING_PARAM_DEEPSEEK_V4
    assert out["supports_reasoning"] is True
    assert out["temperature_policy"] == "fixed_1"


def test_enrich_gateway_model_tags_respects_explicit() -> None:
    out = enrich_gateway_model_tags(
        {"thinking_param": "builtin_reasoning"},
        provider="dashscope",
        real_model="qwen3-32b",
    )
    assert out["thinking_param"] == THINKING_PARAM_BUILTIN


# ---------- Moonshot/Kimi ----------


def test_is_moonshot_model_by_name() -> None:
    assert is_moonshot_model("kimi-for-coding-chat")
    assert is_moonshot_model("kimi-for-coding")
    assert is_moonshot_model("moonshot-v1-128k")
    assert not is_moonshot_model("gpt-4o")
    assert not is_moonshot_model("")


def test_infer_moonshot_by_provider() -> None:
    """provider=moonshot 时自动推断为 builtin reasoning。"""
    assert (
        infer_thinking_param(provider="moonshot", real_model="kimi-for-coding")
        == THINKING_PARAM_BUILTIN
    )


def test_infer_kimi_by_model_name() -> None:
    """即使 provider 为 openai，模型名含 kimi 也能识别。"""
    assert (
        infer_thinking_param(provider="openai", real_model="kimi-for-coding-chat")
        == THINKING_PARAM_BUILTIN
    )


def test_enrich_moonshot_tags_auto_detect() -> None:
    """Moonshot 模型注册时自动推断 supports_reasoning=True。"""
    out = enrich_gateway_model_tags(
        {},
        provider="moonshot",
        real_model="kimi-for-coding",
    )
    assert out["thinking_param"] == THINKING_PARAM_BUILTIN
    assert out["supports_reasoning"] is True
    assert out["temperature_policy"] == "fixed_1"
