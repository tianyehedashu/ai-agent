"""
Agent API - Agent 管理接口
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from models.user import User

router = APIRouter()


class AgentCreate(BaseModel):
    """创建 Agent 请求"""

    name: str = Field(..., min_length=1, max_length=100, description="Agent 名称")
    description: str | None = Field(default=None, max_length=500, description="描述")
    system_prompt: str = Field(..., min_length=1, description="系统提示词")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="模型名称")
    tools: list[str] = Field(default_factory=list, description="启用的工具列表")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大输出Token")
    max_iterations: int = Field(default=20, ge=1, le=100, description="最大迭代次数")


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

    class Config:
        from_attributes = True


@router.get("/", response_model=list[AgentResponse])
async def list_agents(
    current_user: User = Depends(get_current_user),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AgentResponse]:
    """获取用户的 Agent 列表"""
    from services.agent import AgentService

    agent_service = AgentService()
    agents = await agent_service.list_by_user(str(current_user.id), skip=skip, limit=limit)
    return [AgentResponse.model_validate(agent) for agent in agents]


@router.post("/", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    data: AgentCreate,
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """创建新 Agent"""
    from services.agent import AgentService

    agent_service = AgentService()
    agent = await agent_service.create(
        user_id=str(current_user.id),
        **data.model_dump(),
    )
    return AgentResponse.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """获取 Agent 详情"""
    from services.agent import AgentService

    agent_service = AgentService()
    agent = await agent_service.get_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # 检查权限
    if str(agent.user_id) != str(current_user.id) and not agent.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return AgentResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """更新 Agent"""
    from services.agent import AgentService

    agent_service = AgentService()
    agent = await agent_service.get_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # 检查权限
    if str(agent.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # 更新
    update_data = data.model_dump(exclude_unset=True)
    updated_agent = await agent_service.update(agent_id, update_data)

    return AgentResponse.model_validate(updated_agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """删除 Agent"""
    from services.agent import AgentService

    agent_service = AgentService()
    agent = await agent_service.get_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # 检查权限
    if str(agent.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    await agent_service.delete(agent_id)
