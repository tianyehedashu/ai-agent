"""resolve_openai_compatible_models_list_url 纯函数行为。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.upstream.upstream_catalog_policy import (
    resolve_openai_compatible_models_list_url,
)


@pytest.mark.parametrize(
    ("provider", "api_base", "expected_status", "expected_url"),
    [
        ("anthropic", None, "unsupported", None),
        ("openai", None, "ok", "https://api.openai.com/v1/models"),
        ("deepseek", None, "ok", "https://api.deepseek.com/v1/models"),
        ("custom", None, "unsupported", None),
        ("custom", "https://example.com/v1", "ok", "https://example.com/v1/models"),
        (
            "dashscope",
            None,
            "ok",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
        ),
        ("dashscope", "https://x.com/foo", "ok", "https://x.com/foo/models"),
        (
            "zhipuai",
            None,
            "ok",
            "https://open.bigmodel.cn/api/paas/v4/models",
        ),
        (
            "volcengine",
            "https://ark.cn-beijing.volces.com/api/coding",
            "ok",
            "https://ark.cn-beijing.volces.com/api/coding/v3/models",
        ),
        (
            "volcengine",
            None,
            "ok",
            "https://ark.cn-beijing.volces.com/api/v3/models",
        ),
    ],
)
def test_resolve_url(
    provider: str,
    api_base: str | None,
    expected_status: str,
    expected_url: str | None,
) -> None:
    st, url, reason = resolve_openai_compatible_models_list_url(
        provider=provider, api_base=api_base
    )
    assert st == expected_status
    if expected_status == "unsupported":
        assert url is None
        assert reason
    else:
        assert url == expected_url
