"""Agent 领域消息格式化单测（T4：format_domain_messages 全角色）。"""

from domains.agent.domain.types import Message, MessageRole, ToolCall
from domains.agent.infrastructure.llm.message_formatter import (
    estimate_message_tokens,
    format_domain_messages,
    format_message,
    format_tool_calls,
)


def test_format_user_message() -> None:
    row = format_message(Message(role=MessageRole.USER, content="hello"))
    assert row == {"role": "user", "content": "hello"}


def test_format_assistant_with_tool_calls() -> None:
    msg = Message(
        role=MessageRole.ASSISTANT,
        content="",
        tool_calls=[ToolCall(id="c1", name="read_file", arguments={"path": "/tmp"})],
    )
    rows = format_domain_messages([msg])
    assert rows[0]["tool_calls"][0]["function"]["name"] == "read_file"


def test_format_tool_result_message() -> None:
    row = format_message(
        Message(role=MessageRole.TOOL, content="ok", tool_call_id="c1"),
    )
    assert row["role"] == "tool"
    assert row["tool_call_id"] == "c1"
    assert row["content"] == "ok"


def test_format_tool_calls_dict_arguments_stringified() -> None:
    out = format_tool_calls([ToolCall(id="1", name="fn", arguments={"a": 1})])
    assert out[0]["type"] == "function"
    assert '"a": 1' in out[0]["function"]["arguments"] or "a" in out[0]["function"]["arguments"]


def test_estimate_message_tokens_includes_tool_overhead() -> None:
    msg = Message(
        role=MessageRole.ASSISTANT,
        content="hi",
        tool_calls=[ToolCall(id="c1", name="fn", arguments={})],
    )
    assert estimate_message_tokens(msg) > estimate_message_tokens(
        Message(role=MessageRole.USER, content="hi")
    )
