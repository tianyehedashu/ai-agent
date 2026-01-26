"""Agent Domain - Repository Interfaces

定义数据访问的抽象接口，遵循依赖倒置原则。
具体实现由 Infrastructure 层提供。
"""

from domains.agent.domain.interfaces.agent_repository import AgentRepository
from domains.agent.domain.interfaces.message_repository import MessageRepository
from domains.agent.domain.interfaces.session_repository import SessionRepository

__all__ = ["AgentRepository", "MessageRepository", "SessionRepository"]
