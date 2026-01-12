"""
Agent Service - Agent 服务
"""

import uuid
from typing import Any

from sqlalchemy import select

from db.database import get_session_context
from models.agent import Agent


class AgentService:
    """Agent 服务"""

    async def create(
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
        async with get_session_context() as session:
            agent = Agent(
                user_id=uuid.UUID(user_id),
                name=name,
                description=description,
                system_prompt=system_prompt,
                model=model,
                tools=tools or [],
                temperature=temperature,
                max_tokens=max_tokens,
                max_iterations=max_iterations,
            )
            session.add(agent)
            await session.flush()
            await session.refresh(agent)
            return agent

    async def get_by_id(self, agent_id: str) -> Agent | None:
        """通过 ID 获取 Agent"""
        async with get_session_context() as session:
            result = await session.execute(
                select(Agent).where(Agent.id == uuid.UUID(agent_id))
            )
            return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Agent]:
        """获取用户的 Agent 列表"""
        async with get_session_context() as session:
            result = await session.execute(
                select(Agent)
                .where(Agent.user_id == uuid.UUID(user_id))
                .order_by(Agent.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            return list(result.scalars().all())

    async def update(self, agent_id: str, data: dict[str, Any]) -> Agent:
        """更新 Agent"""
        async with get_session_context() as session:
            result = await session.execute(
                select(Agent).where(Agent.id == uuid.UUID(agent_id))
            )
            agent = result.scalar_one_or_none()
            if not agent:
                raise ValueError("Agent not found")

            for key, value in data.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)

            await session.flush()
            await session.refresh(agent)
            return agent

    async def delete(self, agent_id: str) -> None:
        """删除 Agent"""
        async with get_session_context() as session:
            result = await session.execute(
                select(Agent).where(Agent.id == uuid.UUID(agent_id))
            )
            agent = result.scalar_one_or_none()
            if agent:
                await session.delete(agent)
