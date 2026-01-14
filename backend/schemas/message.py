"""
Message Schemas - 消息相关 Schema

提供对话事件、工具调用等数据结构。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatEvent(BaseModel):
    """对话事件

    用于 SSE 流式传输的事件数据。

    Attributes:
        type: 事件类型 (thinking, text, tool_call, tool_result, interrupt, done, error)
        data: 事件数据
        timestamp: 事件时间戳
    """

    model_config = ConfigDict(frozen=True)

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolCallData(BaseModel):
    """工具调用数据"""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResultData(BaseModel):
    """工具结果数据"""

    model_config = ConfigDict(frozen=True)

    tool_call_id: str
    success: bool
    output: str
    error: str | None = None


class InterruptData(BaseModel):
    """中断数据

    Human-in-the-Loop 场景下的中断信息。
    """

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    pending_action: ToolCallData
    reason: str
