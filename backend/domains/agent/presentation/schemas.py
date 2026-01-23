"""
Runtime Presentation Schemas - 运行时表示层模式

包含运行时相关的所有请求/响应模式，如消息、会话等。
"""

# 从同层的 message_schemas 导入
from domains.agent.presentation.message_schemas import (
    AgentEvent,
    ChatEvent,
    ChatEventType,
    DoneEventData,
    ErrorEventData,
    EventType,
    FinalMessage,
    InterruptData,
    SessionEventData,
    TextEventData,
    ThinkingEventData,
    ToolCallData,
    ToolCallEventData,
    ToolResultData,
    ToolResultEventData,
)

# 重新导出，保持向后兼容
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
