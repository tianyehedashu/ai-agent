"""
Session API - 会话管理接口
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_current_user, get_session_service
from api.errors import ACCESS_DENIED, SESSION_NOT_FOUND
from models.user import User
from services.session import SessionService

router = APIRouter()


class SessionCreate(BaseModel):
    """创建会话请求"""

    agent_id: str | None = Field(default=None, description="关联的 Agent ID")
    title: str | None = Field(default=None, max_length=200, description="会话标题")


class SessionResponse(BaseModel):
    """会话响应"""

    id: str
    user_id: str
    agent_id: str | None
    title: str | None
    status: str
    message_count: int
    token_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """消息响应"""

    id: str
    session_id: str
    role: str
    content: str | None
    tool_calls: dict | None
    tool_call_id: str | None
    metadata: dict
    token_count: int | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    agent_id: str | None = None,
) -> list[SessionResponse]:
    """获取用户的会话列表"""
    sessions = await session_service.list_by_user(
        user_id=str(current_user.id),
        skip=skip,
        limit=limit,
        agent_id=agent_id,
    )
    return [SessionResponse.model_validate(s) for s in sessions]


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """创建新会话"""
    session = await session_service.create(
        user_id=str(current_user.id),
        agent_id=data.agent_id,
        title=data.title,
    )
    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """获取会话详情"""
    session = await session_service.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SESSION_NOT_FOUND,
        )

    if str(session.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED,
        )

    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
) -> None:
    """删除会话"""
    session = await session_service.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SESSION_NOT_FOUND,
        )

    if str(session.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED,
        )

    await session_service.delete(session_id)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session_service: SessionService = Depends(get_session_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MessageResponse]:
    """获取会话的消息历史"""
    session = await session_service.get_by_id(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=SESSION_NOT_FOUND,
        )

    if str(session.user_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ACCESS_DENIED,
        )

    messages = await session_service.get_messages(session_id, skip=skip, limit=limit)
    return [MessageResponse.model_validate(m) for m in messages]
