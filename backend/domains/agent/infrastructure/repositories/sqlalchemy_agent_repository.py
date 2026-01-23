"""
SQLAlchemy Agent Repository - Agent 仓储实现

使用 SQLAlchemy 实现 Agent 数据访问"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.repositories.agent_repository import AgentRepository
from domains.agent.infrastructure.models.agent import Agent


class SQLAlchemyAgentRepository(AgentRepository):
    """SQLAlchemy Agent 仓储实现"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
    ) -> Agent:
        """创建 Agent"""
        agent = Agent(
            user_id=user_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            model=model,
            tools=tools or [],
            temperature=temperature,
            max_tokens=max_tokens,
            max_iterations=max_iterations,
        )
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def get_by_id(self, agent_id: uuid.UUID) -> Agent | None:
        """通过 ID 获取 Agent"""
        result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
        return result.scalar_one_or_none()

    async def find_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Agent]:
        """查询用户Agent 列表"""
        result = await self.db.execute(
            select(Agent)
            .where(Agent.user_id == user_id)
            .order_by(Agent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

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
    ) -> Agent | None:
        """更新 Agent"""
        agent = await self.get_by_id(agent_id)
        if not agent:
            return None

        if name is not None:
            agent.name = name
        if description is not None:
            agent.description = description
        if system_prompt is not None:
            agent.system_prompt = system_prompt
        if model is not None:
            agent.model = model
        if tools is not None:
            agent.tools = tools
        if temperature is not None:
            agent.temperature = temperature
        if max_tokens is not None:
            agent.max_tokens = max_tokens
        if max_iterations is not None:
            agent.max_iterations = max_iterations

        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def delete(self, agent_id: uuid.UUID) -> bool:
        """删除 Agent"""
        agent = await self.get_by_id(agent_id)
        if not agent:
            return False

        await self.db.delete(agent)
        return True
