"""
Agent Use Case - Agent 用例
编排 Agent 相关的操作。"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.repositories.agent_repository import AgentRepository
from domains.agent.infrastructure.models.agent import Agent
from domains.agent.infrastructure.repositories import SQLAlchemyAgentRepository
from exceptions import NotFoundError


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """安全地将字符串转换为 UUID"""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


class AgentUseCase:
    """Agent 用例

    协调 Agent 相关的操作。
    """

    def __init__(
        self,
        db: AsyncSession,
        agent_repo: AgentRepository | None = None,
    ) -> None:
        self.db = db
        self.agent_repo = agent_repo or SQLAlchemyAgentRepository(db)

    async def create_agent(
        self,
        user_id: str,
        name: str,
        system_prompt: str,
        description: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        tools: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_iterations: int = 20,
    ) -> Agent:
        """创建 Agent"""
        user_uuid = _safe_uuid(user_id)
        if not user_uuid:
            raise ValueError(f"Invalid user_id format: {user_id}")

        agent = await self.agent_repo.create(
            user_id=user_uuid,
            name=name,
            system_prompt=system_prompt,
            description=description,
            model=model,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
        )

        return agent

    async def get_agent(self, agent_id: str) -> Agent | None:
        """通过 ID 获取 Agent"""
        return await self.agent_repo.get_by_id(uuid.UUID(agent_id))

    async def get_agent_or_raise(self, agent_id: str) -> Agent:
        """通过 ID 获取 Agent，不存在则抛出异常"""
        agent = await self.get_agent(agent_id)
        if not agent:
            raise NotFoundError("Agent", agent_id)
        return agent

    async def list_agents(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Agent]:
        """获取用户的 Agent 列表"""
        user_uuid = _safe_uuid(user_id)
        if not user_uuid:
            return []

        return await self.agent_repo.find_by_user(
            user_id=user_uuid,
            skip=skip,
            limit=limit,
        )

    async def update_agent(
        self,
        agent_id: str,
        name: str | None = None,
        description: str | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        tools: list[str] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_iterations: int | None = None,
    ) -> Agent:
        """更新 Agent"""
        agent = await self.agent_repo.update(
            agent_id=uuid.UUID(agent_id),
            name=name,
            description=description,
            system_prompt=system_prompt,
            model=model,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
        )
        if not agent:
            raise NotFoundError("Agent", agent_id)
        return agent

    async def delete_agent(self, agent_id: str) -> None:
        """删除 Agent"""
        success = await self.agent_repo.delete(uuid.UUID(agent_id))
        if not success:
            raise NotFoundError("Agent", agent_id)
