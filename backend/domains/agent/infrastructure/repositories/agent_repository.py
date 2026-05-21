"""
Agent Repository - Agent 仓储实现

实现 Agent 数据访问，支持自动权限过滤。
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.interfaces.agent_repository import (
    AgentRepository as AgentRepositoryInterface,
)
from domains.agent.infrastructure.models.agent import Agent
from domains.tenancy.application.personal_team_provisioner import PersonalTeamProvisioner
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.iam.permission_context import get_permission_context


class AgentRepository(TenantScopedRepositoryBase[Agent], AgentRepositoryInterface):
    """Agent 仓储实现（``tenant_id`` + ``PermissionContext.team_ids`` 行级过滤）。"""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self.db = db

    @property
    def model_class(self) -> type[Agent]:
        """返回模型类"""
        return Agent

    # 不支持匿名用户，使用默认的 anonymous_user_id_column = None

    async def create(
        self,
        user_id: uuid.UUID,
        name: str,
        system_prompt: str,
        description: str | None = None,
        model: str = "claude-3-5-sonnet",
        tools: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_iterations: int = 20,
    ) -> Agent:
        """创建 Agent"""
        tenant_id = await PersonalTeamProvisioner(self.db).ensure_personal_team(user_id)
        agent = Agent(
            tenant_id=tenant_id,
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
        """通过 ID 获取 Agent（自动检查所有权）"""
        return await self.get_in_tenants(agent_id)

    async def find_by_user(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Agent]:
        """查询用户 Agent 列表（自动过滤当前用户的数据）

        Args:
            user_id: 注册用户 ID（必须与 PermissionContext 一致）
            skip: 跳过记录数
            limit: 返回记录数

        Returns:
            Agent 实体列表

        Raises:
            ValueError: 如果传递的 user_id 与 PermissionContext 不一致
        """
        # 验证传递的参数与 PermissionContext 一致（防止授权漏洞）
        # 管理员可以查询任何用户的数据，所以跳过验证
        ctx = get_permission_context()
        if ctx and not ctx.is_admin and ctx.user_id != user_id:
            raise ValueError(
                f"user_id parameter ({user_id}) does not match PermissionContext ({ctx.user_id}). "
                "This may indicate an authorization bug."
            )

        return await self.find_for_tenants(
            skip=skip,
            limit=limit,
            order_by="created_at",
            order_desc=True,
        )

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

    async def count_total(self) -> int:
        """统计 Agent 总数"""
        result = await self.db.execute(select(func.count(Agent.id)))
        return result.scalar() or 0

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """统计 personal team 下 Agent 数（与 ``find_by_user`` 可见范围一致）。"""
        tenant_id = await PersonalTeamProvisioner(self.db).ensure_personal_team(user_id)
        result = await self.db.execute(
            select(func.count(Agent.id)).where(Agent.tenant_id == tenant_id)
        )
        return result.scalar() or 0
