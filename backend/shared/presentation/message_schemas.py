"""
Message Schemas - Message-related schemas

API layer message schemas, reusing the unified event system from core/types.py.

Architecture notes:
- Event types and data models are unified in core/types.py
- ChatEvent is an alias for AgentEvent, used in API layer
- Retains some API-specific data structures (e.g., InterruptData)
"""

from pydantic import BaseModel, ConfigDict

from shared.types import (
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
# ChatEvent - Alias for AgentEvent, used in API layer
# =============================================================================

# ChatEvent directly uses AgentEvent to avoid duplicate definitions and conversions
# EventType enum inherits from str, automatically converts to string during JSON serialization
ChatEvent = AgentEvent

# ChatEventType is an alias for EventType, maintaining API layer naming consistency
ChatEventType = EventType


# =============================================================================
# API-specific data structures
# =============================================================================


class ToolCallData(ToolCall):
    """Tool call data (API layer alias)"""

    pass


class ToolResultData(ToolResult):
    """Tool result data (API layer alias)"""

    pass


class InterruptData(BaseModel):
    """Interrupt data

    Interrupt information for Human-in-the-Loop scenarios.
    """

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    pending_action: ToolCallData
    reason: str


# =============================================================================
# Export all types for external use
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
