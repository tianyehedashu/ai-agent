"""
Agent Repository Interface - Agent 仓储接口

定义 Agent 数据访问的抽象接口。
"""

from abc import ABC, abstractmethod
from typing import Protocol
import uuid


class AgentEntity(Protocol):
    """Agent 实体协议"""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    model: str
    tools: list[str]
    temperature: float
    max_tokens: int
    max_iterations: int
    is_public: bool


class AgentRepository(ABC):
    """Agent 仓储接口"""

    @abstractmethod
    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        system_prompt: str,
        description: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        tools: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_iterations: int = 20,
    ) -> AgentEntity:
        """创建 Agent"""
        ...

    @abstractmethod
    async def get_by_id(self, agent_id: uuid.UUID) -> AgentEntity | None:
        """通过 ID 获取 Agent"""
        ...

    @abstractmethod
    async def find_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[AgentEntity]:
        """查询用户的 Agent 列表"""
        ...

    @abstractmethod
    async def update(
        self,
        agent_id: uuid.UUID,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_iterations: int | None = None,
    ) -> AgentEntity | None:
        """更新 Agent"""
        ...

    @abstractmethod
    async def delete(self, agent_id: uuid.UUID) -> bool:
        """删除 Agent"""
        ...
