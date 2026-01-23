"""
Runtime Presentation Schemas - 运行时表示层模式

包含运行时相关的所有请求/响应模式，如消息、会话等。

注意：ChatEvent 已统一在 shared/presentation/message_schemas.py 中定义，
这里仅做重新导出以保持向后兼容。
"""

# 从共享层导入，避免重复定义
from shared.presentation.message_schemas import (
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
