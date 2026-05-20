"""Agent LangChain 消息适配单测（T4：convert_langchain_messages 全角色）。"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from domains.agent.infrastructure.llm.langchain_messages import (
    convert_langchain_message,
    convert_langchain_messages,
)


def test_convert_human_message() -> None:
    row = convert_langchain_message(HumanMessage(content="hi"))
    assert row["role"] == "user"
    assert row["content"] == "hi"


def test_convert_ai_message_with_tool_calls() -> None:
    msg = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "read_file",
                "args": {"path": "/tmp"},
                "id": "call_1",
                "type": "tool_call",
            }
        ],
    )
    row = convert_langchain_message(msg)
    assert row["role"] == "assistant"
    assert row["tool_calls"][0]["function"]["name"] == "read_file"
    assert "path" in row["tool_calls"][0]["function"]["arguments"]


def test_convert_tool_message() -> None:
    row = convert_langchain_message(
        ToolMessage(content="file contents", tool_call_id="call_1"),
    )
    assert row == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "file contents",
    }


def test_convert_langchain_messages_with_system() -> None:
    rows = convert_langchain_messages(
        [HumanMessage(content="hi")],
        system_prompt="sys",
    )
    assert rows[0]["role"] == "system"
    assert rows[1]["role"] == "user"
