"""
Agent Service - Agent 服务

提供 Agent 的创建、查询、更新、删除功能。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions import NotFoundError
from models.agent import Agent


def safe_uuid(value: str | None) -> uuid.UUID | None:
    """安全地将字符串转换为 UUID

    Args:
        value: 要转换的字符串

    Returns:
        UUID 对象或 None（如果值无效）
    """
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


class AgentService:
    """Agent 服务

    管理 Agent 的完整生命周期。

    Attributes:
        db: 数据库会话
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
        """创建 Agent

        Args:
            user_id: 用户 ID
            name: Agent 名称
            system_prompt: 系统提示词
            description: 描述（可选）
            model: 模型名称
            tools: 启用的工具列表
            temperature: 温度参数
            max_tokens: 最大输出 Token
            max_iterations: 最大迭代次数

        Returns:
            创建的 Agent 对象
        """
        user_uuid = safe_uuid(user_id)
        if not user_uuid:
            raise ValueError(f"Invalid user_id format: {user_id}")

        agent = Agent(
            user_id=user_uuid,
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

    async def get_by_id(self, agent_id: str) -> Agent | None:
        """通过 ID 获取 Agent

        Args:
            agent_id: Agent ID

        Returns:
            Agent 对象或 None
        """
        result = await self.db.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, agent_id: str) -> Agent:
        """通过 ID 获取 Agent，不存在则抛出异常

        Args:
            agent_id: Agent ID

        Returns:
            Agent 对象

        Raises:
            NotFoundError: Agent 不存在时
        """
        agent = await self.get_by_id(agent_id)
        if not agent:
            raise NotFoundError("Agent", agent_id)
        return agent

    async def list_by_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Agent]:
        """获取用户的 Agent 列表

        Args:
            user_id: 用户 ID
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            Agent 列表
        """
        # 检查 user_id 是否为有效的 UUID（匿名用户会返回空列表）
        user_uuid = safe_uuid(user_id)
        if not user_uuid:
            return []

        result = await self.db.execute(
            select(Agent)
            .where(Agent.user_id == user_uuid)
            .order_by(Agent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(
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
        """更新 Agent

        Args:
            agent_id: Agent ID
            name: 新名称（可选）
            description: 新描述（可选）
            system_prompt: 新系统提示词（可选）
            model: 新模型（可选）
            tools: 新工具列表（可选）
            temperature: 新温度参数（可选）
            max_tokens: 新最大 Token（可选）
            max_iterations: 新最大迭代次数（可选）

        Returns:
            更新后的 Agent

        Raises:
            NotFoundError: Agent 不存在时
        """
        agent = await self.get_by_id_or_raise(agent_id)

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

    async def delete(self, agent_id: str) -> None:
        """删除 Agent

        Args:
            agent_id: Agent ID

        Raises:
            NotFoundError: Agent 不存在时
        """
        agent = await self.get_by_id_or_raise(agent_id)
        await self.db.delete(agent)
