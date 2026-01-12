"""
Message Schemas
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatEvent(BaseModel):
    """对话事件"""

    type: str  # thinking, text, tool_call, tool_result, interrupt, done, error
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolCallData(BaseModel):
    """工具调用数据"""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolResultData(BaseModel):
    """工具结果数据"""

    tool_call_id: str
    success: bool
    output: str
    error: str | None = None


class InterruptData(BaseModel):
    """中断数据"""

    checkpoint_id: str
    pending_action: ToolCallData
    reason: str
