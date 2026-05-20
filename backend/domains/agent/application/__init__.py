"""Agent Domain - Application Layer"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domains.agent.application.agent_use_case import AgentUseCase
    from domains.agent.application.chat_use_case import ChatUseCase
    from domains.agent.application.ports import VideoTaskApplicationPort

__all__ = ["AgentUseCase", "ChatUseCase", "VideoTaskApplicationPort"]


def __getattr__(name: str):
    if name == "AgentUseCase":
        from domains.agent.application.agent_use_case import AgentUseCase

        return AgentUseCase
    if name == "ChatUseCase":
        from domains.agent.application.chat_use_case import ChatUseCase

        return ChatUseCase
    if name == "VideoTaskApplicationPort":
        from domains.agent.application.ports import VideoTaskApplicationPort

        return VideoTaskApplicationPort
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
