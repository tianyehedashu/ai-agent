"""custom_logger：JSONB 字段须可序列化（含 LiteLLM Usage 对象）。"""

from __future__ import annotations

import json
from types import SimpleNamespace

from domains.gateway.infrastructure.callbacks.custom_logger import (
    _jsonb_safe_dict,
    _metadata_extra_non_gateway,
)


class _UsageLike:
    """模拟 LiteLLM/OpenAI Usage（非 Pydantic，仅属性）。"""

    def __init__(self) -> None:
        self.prompt_tokens = 12
        self.completion_tokens = 34
        self.total_tokens = 46


def test_metadata_extra_serializes_usage_object() -> None:
    metadata = {
        "gateway_team_id": "00000000-0000-4000-8000-000000000001",
        "usage": _UsageLike(),
        "trace_id": "abc",
    }
    extra = _metadata_extra_non_gateway(metadata)
    assert extra is not None
    assert extra["trace_id"] == "abc"
    assert extra["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 34,
        "total_tokens": 46,
    }
    json.dumps(extra)


def test_jsonb_safe_dict_handles_nested_objects() -> None:
    payload = {
        "nested": {"usage": _UsageLike()},
        "items": [SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)],
    }
    safe = _jsonb_safe_dict(payload)
    assert safe is not None
    assert safe["nested"]["usage"]["total_tokens"] == 46
    json.dumps(safe)
