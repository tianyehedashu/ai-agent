"""UpstreamAdapter 单元测试。"""

from domains.gateway.application.model_or_route_resolution import ResolvedModelName
from domains.gateway.application.upstream_adapter import UpstreamAdapter


class _FakeRecord:
    def __init__(
        self,
        *,
        provider: str = "deepseek",
        real_model: str = "deepseek-reasoner",
        tags: dict | None = None,
    ) -> None:
        self.provider = provider
        self.real_model = real_model
        self.tags = tags or {"context_window": 8192}


def test_deepseek_reasoner_pads_reasoning_content() -> None:
    record = _FakeRecord()
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    kwargs = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [{"id": "1", "type": "function", "function": {"name": "x"}}],
            }
        ],
        "max_tokens": 1000,
    }
    out = UpstreamAdapter().adapt(kwargs, client_model="deepseek-reasoner", resolved=resolved)
    msg = out["messages"][0]
    assert "reasoning_content" in msg


def test_json_mode_stripped_when_unsupported() -> None:
    out = UpstreamAdapter().adapt(
        {"response_format": {"type": "json_object"}, "max_tokens": 100},
        client_model="gpt-4",
        resolved=ResolvedModelName(
            record=_FakeRecord(
                provider="openai",
                real_model="gpt-4",
                tags={"supports_json_mode": False},
            ),
            route=None,
            via_route=None,
        ),
    )
    assert "response_format" not in out


def test_tools_stripped_when_unsupported() -> None:
    out = UpstreamAdapter().adapt(
        {
            "tools": [{"type": "function", "function": {"name": "f"}}],
            "tool_choice": "auto",
            "max_tokens": 100,
        },
        client_model="gpt-4",
        resolved=ResolvedModelName(
            record=_FakeRecord(
                provider="openai",
                real_model="gpt-4",
                tags={"supports_tools": False},
            ),
            route=None,
            via_route=None,
        ),
    )
    assert "tools" not in out
    assert "tool_choice" not in out


def test_reasoning_model_locks_temperature() -> None:
    out = UpstreamAdapter().adapt(
        {"temperature": 0.2, "max_tokens": 100},
        client_model="deepseek-reasoner",
        resolved=ResolvedModelName(
            record=_FakeRecord(tags={"supports_reasoning": True}),
            route=None,
            via_route=None,
        ),
    )
    assert out["temperature"] == 1.0


def test_max_tokens_clamped_to_tag_limit() -> None:
    out = UpstreamAdapter().adapt(
        {"max_tokens": 99999},
        client_model="deepseek-chat",
        resolved=ResolvedModelName(
            record=_FakeRecord(provider="deepseek", tags={"context_window": 8192}),
            route=None,
            via_route=None,
        ),
    )
    assert out["max_tokens"] == 8192
