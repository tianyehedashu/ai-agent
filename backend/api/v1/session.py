"""
Session API - 会话管理接口
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from api.deps import AuthUser, check_ownership, get_session_service
from services.session import SessionService

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class SessionCreate(BaseModel):
    """创建会话请求"""

    model_config = ConfigDict(strict=True)

    agent_id: str | None = Field(default=None, description="关联的 Agent ID")
    title: str | None = Field(default=None, max_length=200, description="会话标题")


class SessionUpdate(BaseModel):
    """更新会话请求"""

    title: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class SessionResponse(BaseModel):
    """会话响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    agent_id: str | None
    title: str | None
    status: str
    message_count: int
    token_count: int
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    """消息响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    content: str | None
    tool_calls: dict | None
    tool_call_id: str | None
    metadata: dict
    token_count: int | None
    created_at: datetime


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    current_user: AuthUser,
    session_service: SessionService = Depends(get_session_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    agent_id: str | None = None,
) -> list[SessionResponse]:
    """获取用户的会话列表"""
    sessions = await session_service.list_by_user(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        agent_id=agent_id,
    )
    return [SessionResponse.model_validate(s) for s in sessions]


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    current_user: AuthUser,
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """创建新会话"""
    session = await session_service.create(
        user_id=current_user.id,
        agent_id=data.agent_id,
        title=data.title,
    )
    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """获取会话详情"""
    session = await session_service.get_by_id_or_raise(session_id)

    # 检查权限
    check_ownership(str(session.user_id), current_user.id, "Session")

    return SessionResponse.model_validate(session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    data: SessionUpdate,
    current_user: AuthUser,
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """更新会话"""
    session = await session_service.get_by_id_or_raise(session_id)

    # 检查权限
    check_ownership(str(session.user_id), current_user.id, "Session")

    # 更新
    updated_session = await session_service.update(
        session_id=session_id,
        title=data.title,
        status=data.status,
    )

    return SessionResponse.model_validate(updated_session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionService = Depends(get_session_service),
) -> None:
    """删除会话"""
    session = await session_service.get_by_id_or_raise(session_id)

    # 检查权限
    check_ownership(str(session.user_id), current_user.id, "Session")

    await session_service.delete(session_id)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionService = Depends(get_session_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MessageResponse]:
    """获取会话的消息历史"""
    session = await session_service.get_by_id_or_raise(session_id)

    # 检查权限
    check_ownership(str(session.user_id), current_user.id, "Session")

    messages = await session_service.get_messages(session_id, skip=skip, limit=limit)
    return [MessageResponse.model_validate(m) for m in messages]
