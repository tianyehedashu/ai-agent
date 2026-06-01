"""upstream_type_inference 单元测试。"""

from __future__ import annotations

import pytest

from domains.gateway.domain.upstream_type_inference import (
    filter_valid_personal_model_types,
    infer_upstream_model_types,
)


@pytest.mark.parametrize(
    ("upstream_id", "expected"),
    [
        ("gpt-4o-mini", ("text", "image")),
        ("claude-3-5-sonnet-20241022", ("text", "image")),
        ("qwen-vl-max", ("text", "image")),
        ("dall-e-3", ("image_gen",)),
        ("sora-2", ("video",)),
        ("text-embedding-3-small", ()),
        ("bge-reranker-v2", ()),
        ("gpt-4o", ("text", "image")),
        ("generic-model", ("text",)),
        ("kimi-k2.6", ("text", "image")),
    ],
)
def test_infer_upstream_model_types(upstream_id: str, expected: tuple[str, ...]) -> None:
    assert infer_upstream_model_types("openai", upstream_id) == expected


def test_filter_valid_personal_model_types() -> None:
    assert filter_valid_personal_model_types(("text", "image", "bogus")) == ("text", "image")
    assert filter_valid_personal_model_types(()) == ()
