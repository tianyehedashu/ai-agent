"""
Agent API - Agent 管理接口
"""

from datetime import datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from domains.agent_catalog.application import AgentUseCase
from shared.presentation.deps import (
    RequiredAuthUser,
    check_ownership,
    check_ownership_or_public,
    get_agent_service,
)

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class AgentCreate(BaseModel):
    """创建 Agent 请求"""

    model_config = ConfigDict(strict=True)

    name: str = Field(..., min_length=1, max_length=100, description="Agent 名称")
    description: str | None = Field(default=None, max_length=500, description="描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示)
    model: str = Field(default="claude-3-5-sonnet-20241022", description="模型名称")
    tools: list[str] = Field(default_factory=list, description="启用的工具列)
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大输出Token")
    max_iterations: int = Field(default=20, ge=1, le=100, description="最大迭代次)


class AgentUpdate(BaseModel):
    """更新 Agent 请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1)
    model: str | None = None
    tools: list[str] | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=128000)
    max_iterations: int | None = Field(default=None, ge=1, le=100)


class AgentResponse(BaseModel):
    """Agent 响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    system_prompt: str
    model: str
    tools: list[str]
    temperature: float
    max_tokens: int
    max_iterations: int
    is_public: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: uuid.UUID | str) -> str:
        """?UUID 转换为字符串"""
        if isinstance(v, uuid.UUID):
            return str(v)
        return v


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/", response_model=list[AgentResponse])
async def list_agents(
    current_user: RequiredAuthUser,
    agent_service: AgentUseCase = Depends(get_agent_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AgentResponse]:
    """获取用户Agent 列表"""
    agents = await agent_service.list_agents(current_user.id, skip=skip, limit=limit)
    return [AgentResponse.model_validate(agent, from_attributes=True) for agent in agents]


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    current_user: RequiredAuthUser,
    agent_service: AgentUseCase = Depends(get_agent_service),
) -> AgentResponse:
    """创建Agent"""
    agent = await agent_service.create_agent(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        model=data.model,
        tools=data.tools,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        max_iterations=data.max_iterations,
    )
    return AgentResponse.model_validate(agent, from_attributes=True)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: RequiredAuthUser,
    agent_service: AgentUseCase = Depends(get_agent_service),
) -> AgentResponse:
    """获取 Agent 详情"""
    agent = await agent_service.get_agent_or_raise(agent_id)

    check_ownership_or_public(
        str(agent.user_id),
        current_user.id,
        agent.is_public,
        "Agent",
    )

    return AgentResponse.model_validate(agent, from_attributes=True)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    current_user: RequiredAuthUser,
    agent_service: AgentUseCase = Depends(get_agent_service),
) -> AgentResponse:
    """更新 Agent"""
    agent = await agent_service.get_agent_or_raise(agent_id)
    check_ownership(str(agent.user_id), current_user.id, "Agent")

    updated_agent = await agent_service.update_agent(
        agent_id=agent_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        model=data.model,
        tools=data.tools,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        max_iterations=data.max_iterations,
    )

    return AgentResponse.model_validate({**updated_agent.__dict__, "id": str(updated_agent.id)})


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: RequiredAuthUser,
    agent_service: AgentUseCase = Depends(get_agent_service),
) -> None:
    """删除 Agent"""
    agent = await agent_service.get_agent_or_raise(agent_id)
    check_ownership(str(agent.user_id), current_user.id, "Agent")
    await agent_service.delete_agent(agent_id)
