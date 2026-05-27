"""Catalog thinking_param 标签审计（app.toml 同步逻辑）。"""

from __future__ import annotations

from domains.gateway.application.config_catalog_sync import build_tags_from_seed_model
from domains.gateway.domain.catalog_seed_model import CatalogSeedModel
from domains.gateway.domain.thinking_param import (
    THINKING_PARAM_ANTHROPIC,
    THINKING_PARAM_BUILTIN,
    THINKING_PARAM_DASHSCOPE,
    THINKING_PARAM_DEEPSEEK_V4,
    THINKING_PARAM_NONE,
)


def _tags(model: CatalogSeedModel) -> dict:
    return build_tags_from_seed_model(model)


def test_deepseek_reasoner_builtin_reasoning() -> None:
    tags = _tags(
        CatalogSeedModel(
            id="deepseek/deepseek-reasoner",
            name="DeepSeek Reasoner (R1)",
            provider="deepseek",
            litellm_model="deepseek/deepseek-reasoner",
            supports_reasoning=True,
            thinking_param="builtin_reasoning",
        )
    )
    assert tags["thinking_param"] == THINKING_PARAM_BUILTIN
    assert tags["supports_reasoning"] is True
    assert tags["temperature_policy"] == "fixed_1"


def test_qwen3_dashscope_enable_thinking() -> None:
    tags = _tags(
        CatalogSeedModel(
            id="dashscope/qwen3-32b",
            name="Qwen3 32B",
            provider="dashscope",
            litellm_model="dashscope/qwen3-32b",
            supports_reasoning=True,
            thinking_param="dashscope_enable_thinking",
        )
    )
    assert tags["thinking_param"] == THINKING_PARAM_DASHSCOPE
    assert tags["supports_reasoning"] is True


def test_qwq_builtin_reasoning() -> None:
    tags = _tags(
        CatalogSeedModel(
            id="dashscope/qwq-32b-preview",
            name="QwQ 32B",
            provider="dashscope",
            litellm_model="dashscope/qwq-32b-preview",
            supports_reasoning=True,
            thinking_param="builtin_reasoning",
        )
    )
    assert tags["thinking_param"] == THINKING_PARAM_BUILTIN


def test_claude_35_sonnet_no_extended_thinking() -> None:
    tags = _tags(
        CatalogSeedModel(
            id="claude-3-5-sonnet",
            name="Claude 3.5 Sonnet",
            provider="anthropic",
            litellm_model="claude-3-5-sonnet-20241022",
        )
    )
    assert tags["thinking_param"] == THINKING_PARAM_NONE
    assert tags["supports_reasoning"] is False


def test_claude_opus_47_anthropic_extended() -> None:
    tags = _tags(
        CatalogSeedModel(
            id="claude-opus-4-7",
            name="Claude Opus 4.7",
            provider="anthropic",
            litellm_model="claude-opus-4-7",
            supports_reasoning=True,
            thinking_param="anthropic_extended",
        )
    )
    assert tags["thinking_param"] == THINKING_PARAM_ANTHROPIC
    assert tags["supports_reasoning"] is True


def test_deepseek_v4_pro_extra_body_thinking() -> None:
    tags = _tags(
        CatalogSeedModel(
            id="deepseek/deepseek-v4-pro",
            name="DeepSeek V4 Pro",
            provider="deepseek",
            litellm_model="deepseek/deepseek-v4-pro",
            supports_reasoning=True,
            thinking_param="deepseek_v4_thinking",
        )
    )
    assert tags["thinking_param"] == THINKING_PARAM_DEEPSEEK_V4
    assert tags["supports_reasoning"] is True
    assert tags["temperature_policy"] == "fixed_1"
