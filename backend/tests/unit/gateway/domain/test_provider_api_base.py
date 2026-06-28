"""provider_api_base 纯函数测试。"""

from __future__ import annotations

from domains.gateway.domain.provider.provider_api_base import (
    get_default_api_base,
    resolve_effective_api_base,
)


def test_get_default_api_base_known_providers() -> None:
    assert get_default_api_base("zhipuai") == "https://open.bigmodel.cn/api/paas/v4"
    assert get_default_api_base("dashscope") == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert get_default_api_base("ZHIPUAI") == "https://open.bigmodel.cn/api/paas/v4"


def test_get_default_api_base_requires_explicit_config() -> None:
    assert get_default_api_base("anthropic") is None
    assert get_default_api_base("custom") is None
    assert get_default_api_base("") is None
    assert get_default_api_base("unknown") is None


def test_resolve_effective_api_base_prefers_explicit() -> None:
    explicit = "https://open.bigmodel.cn/api/coding/paas/v4"
    assert resolve_effective_api_base("zhipuai", explicit) == explicit


def test_resolve_effective_api_base_falls_back_to_default() -> None:
    assert resolve_effective_api_base("zhipuai", None) == get_default_api_base("zhipuai")
    assert resolve_effective_api_base("zhipuai", "  ") == get_default_api_base("zhipuai")
