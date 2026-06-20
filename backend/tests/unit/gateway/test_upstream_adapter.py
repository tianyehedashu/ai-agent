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


def test_kimi_for_coding_locks_temperature_when_thinking_disabled() -> None:
    out = UpstreamAdapter().adapt(
        {"temperature": 0.2, "max_tokens": 100},
        client_model="my-kimi-code",
        resolved=ResolvedModelName(
            record=_FakeRecord(
                provider="moonshot",
                real_model="my-custom-code-model",
                tags={
                    "thinking_param": "none",
                    "thinking_param_locked": True,
                    "upstream_profile_id": "moonshot.coding_plan",
                },
            ),
            route=None,
            via_route=None,
        ),
        credential_profile_id="moonshot.coding_plan",
    )
    assert out["temperature"] == 1.0


def test_coding_plan_profile_locks_temperature_without_tag() -> None:
    out = UpstreamAdapter().adapt(
        {"temperature": 0.2, "max_tokens": 100},
        client_model="alias-only",
        resolved=ResolvedModelName(
            record=_FakeRecord(
                provider="moonshot",
                real_model="totally-new-model-id",
                tags={"thinking_param": "none", "thinking_param_locked": True},
            ),
            route=None,
            via_route=None,
        ),
        credential_profile_id="moonshot.coding_plan",
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


def test_coding_agent_ua_injected_for_coding_plan_profile() -> None:
    out = UpstreamAdapter().adapt(
        {"max_tokens": 100},
        client_model="kimi-k2-0711",
        resolved=ResolvedModelName(
            record=_FakeRecord(provider="moonshot"),
            route=None,
            via_route=None,
        ),
        credential_profile_id="moonshot.coding_plan",
    )
    assert out["extra_headers"]["User-Agent"] == "claude-cli/2.1.161"


def test_coding_agent_ua_fallback_by_real_model_when_profile_is_default() -> None:
    """profile 为 default 但 real_model 是 kimi-for-coding，仍应注入 UA。"""
    out = UpstreamAdapter().adapt(
        {"max_tokens": 100},
        client_model="my-kimi-code-alias",
        resolved=ResolvedModelName(
            record=_FakeRecord(provider="moonshot", real_model="kimi-for-coding"),
            route=None,
            via_route=None,
        ),
        credential_profile_id="moonshot.default",
    )
    assert out["extra_headers"]["User-Agent"] == "claude-cli/2.1.161"


def test_coding_agent_ua_not_injected_for_default_profile() -> None:
    out = UpstreamAdapter().adapt(
        {"max_tokens": 100},
        client_model="moonshot-v1-8k",
        resolved=ResolvedModelName(
            record=_FakeRecord(provider="moonshot", real_model="moonshot-v1-8k"),
            route=None,
            via_route=None,
        ),
        credential_profile_id="moonshot.default",
    )
    assert "extra_headers" not in out or "User-Agent" not in (out.get("extra_headers") or {})


def test_flatten_text_only_content_array_for_non_vision_provider() -> None:
    record = _FakeRecord(provider="deepseek", real_model="deepseek-chat")
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    kwargs = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "world"}]},
        ],
        "max_tokens": 100,
    }
    out = UpstreamAdapter().adapt(kwargs, client_model="deepseek-chat", resolved=resolved)
    assert out["messages"][0]["content"] == "hello"
    assert out["messages"][1]["content"] == "world"


def test_preserve_mixed_content_array_for_non_vision_provider() -> None:
    record = _FakeRecord(provider="deepseek", real_model="deepseek-chat")
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    kwargs = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": "http://example.com/img.png"}},
                ],
            },
        ],
        "max_tokens": 100,
    }
    out = UpstreamAdapter().adapt(kwargs, client_model="deepseek-chat", resolved=resolved)
    assert isinstance(out["messages"][0]["content"], list)
    assert out["messages"][0]["content"][0]["type"] == "text"


def test_skip_flatten_for_vision_provider() -> None:
    record = _FakeRecord(
        provider="openai",
        real_model="gpt-4o",
        tags={"context_window": 8192, "supports_vision": True},
    )
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    kwargs = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        ],
        "max_tokens": 100,
    }
    out = UpstreamAdapter().adapt(kwargs, client_model="gpt-4o", resolved=resolved)
    assert isinstance(out["messages"][0]["content"], list)


def test_moonshot_empty_user_message_padded_to_space() -> None:
    """Moonshot 拒绝空 user content，应填充为单个空格保留轮次。"""
    record = _FakeRecord(provider="moonshot", real_model="kimi-for-coding")
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    kwargs = {
        "messages": [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "   "},
            {"role": "user", "content": None},
        ],
        "max_tokens": 100,
    }
    out = UpstreamAdapter().adapt(kwargs, client_model="kimi-for-coding", resolved=resolved)
    messages = out["messages"]
    assert messages[0]["content"] == " "
    assert messages[1]["content"] == "ok"
    assert messages[2]["content"] == " "
    assert messages[3]["content"] == " "


def test_non_moonshot_empty_user_message_left_unchanged() -> None:
    """非 Moonshot provider 不应用该兜底，避免意外修改请求体。"""
    record = _FakeRecord(provider="deepseek", real_model="deepseek-chat")
    resolved = ResolvedModelName(record=record, route=None, via_route=None)
    kwargs = {
        "messages": [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "ok"},
        ],
        "max_tokens": 100,
    }
    out = UpstreamAdapter().adapt(kwargs, client_model="deepseek-chat", resolved=resolved)
    assert out["messages"][0]["content"] == ""
    assert out["messages"][1]["content"] == "ok"


def test_adapt_returns_original_when_resolved_is_none_and_no_ua() -> None:
    """resolved=None 且无 coding_agent UA 注入时返回原 kwargs 引用。"""
    kwargs = {"model": "gpt-4", "messages": []}
    out = UpstreamAdapter().adapt(kwargs, client_model="gpt-4", resolved=None)
    assert out is kwargs


def test_adapt_returns_new_object_when_changes_needed() -> None:
    """需要改写时返回新对象，且不污染原 kwargs。"""
    kwargs = {"response_format": {"type": "json_object"}, "max_tokens": 100}
    out = UpstreamAdapter().adapt(
        kwargs,
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
    assert out is not kwargs
    assert "response_format" in kwargs
    assert "response_format" not in out
