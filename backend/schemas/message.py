"""
Message Schemas - 消息相关 Schema

API 层的消息 Schema，复用 core/types.py 中的统一事件系统。

架构说明：
- 事件类型和数据模型统一定义在 core/types.py
- ChatEvent 是 AgentEvent 的别名，用于 API 层
- 保留部分 API 特定的数据结构（如 InterruptData）
"""

from pydantic import BaseModel, ConfigDict

from core.types import (
    AgentEvent,
    DoneEventData,
    ErrorEventData,
    EventType,
    FinalMessage,
    SessionEventData,
    TextEventData,
    ThinkingEventData,
    ToolCall,
    ToolCallEventData,
    ToolResult,
    ToolResultEventData,
)

# =============================================================================
# ChatEvent - AgentEvent 的别名，用于 API 层
# =============================================================================

# ChatEvent 直接使用 AgentEvent，避免重复定义和转换
# EventType 枚举继承自 str，JSON 序列化时自动转换为字符串
ChatEvent = AgentEvent

# ChatEventType 是 EventType 的别名，保持 API 层命名一致性
ChatEventType = EventType


# =============================================================================
# API 特定的数据结构
# =============================================================================


class ToolCallData(ToolCall):
    """工具调用数据（API 层别名）"""

    pass


class ToolResultData(ToolResult):
    """工具结果数据（API 层别名）"""

    pass


class InterruptData(BaseModel):
    """中断数据

    Human-in-the-Loop 场景下的中断信息。
    """

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    pending_action: ToolCallData
    reason: str


# =============================================================================
# 导出所有类型，方便外部使用
# =============================================================================

__all__ = [
    "AgentEvent",
    "ChatEvent",
    "ChatEventType",
    "DoneEventData",
    "ErrorEventData",
    "EventType",
    "FinalMessage",
    "InterruptData",
    "SessionEventData",
    "TextEventData",
    "ThinkingEventData",
    "ToolCallData",
    "ToolCallEventData",
    "ToolResultData",
    "ToolResultEventData",
]
