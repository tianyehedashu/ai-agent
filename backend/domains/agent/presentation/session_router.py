"""
Session API - 会话管理接口
"""

from datetime import datetime
import json
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError

from domains.agent.application import SessionUseCase, TitleUseCase
from domains.identity.domain.types import Principal
from domains.identity.presentation.deps import (
    AuthUser,
    check_session_ownership,
)
from libs.api.deps import get_session_service, get_title_service

router = APIRouter()


def _get_user_ids(current_user: AuthUser) -> tuple[str | None, str | None]:
    """从当前用户获取 user_id 或 anonymous_user_id

    Returns:
        (user_id, anonymous_user_id) 元组，根据用户类型只有一个不为 None
    """
    if current_user.is_anonymous:
        return None, Principal.extract_anonymous_id(current_user.id)
    return current_user.id, None


# =============================================================================
# Request/Response Schemas
# =============================================================================


class SessionCreate(BaseModel):
    """创建会话请求"""

    model_config = ConfigDict(strict=True)

    agent_id: str | None = Field(default=None, description="关联Agent ID")
    title: str | None = Field(default=None, max_length=200, description="会话标题")


class SessionUpdate(BaseModel):
    """更新会话请求"""

    title: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class SessionResponse(BaseModel):
    """会话响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None  # 注册用户 ID（匿名用户为 None）
    anonymous_user_id: str | None  # 匿名用户 ID（注册用户为 None）
    agent_id: str | None
    title: str | None
    status: str
    message_count: int
    token_count: int
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "user_id", "agent_id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: uuid.UUID | str | None) -> str | None:
        """将 UUID 转换为字符串"""
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return str(v)
        return v


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

    @field_validator("id", "session_id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: uuid.UUID | str) -> str:
        """将 UUID 转换为字符串"""
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    @field_validator("metadata", "tool_calls", mode="before")
    @classmethod
    def convert_jsonb_to_dict(cls, v: Any) -> dict | None:
        """将 JSONB 字段转换为字典"""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        try:
            json_str = json.dumps(v, default=str)
            return json.loads(json_str)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        if hasattr(v, "data"):
            data = v.data
            if isinstance(data, dict):
                return data
        try:
            if hasattr(v, "__dict__") and v.__dict__:
                return dict(v.__dict__)
        except (TypeError, AttributeError):
            pass
        return {}


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    current_user: AuthUser,
    session_service: SessionUseCase = Depends(get_session_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    agent_id: str | None = None,
) -> list[SessionResponse]:
    """获取用户的会话列表"""
    user_id, anonymous_user_id = _get_user_ids(current_user)
    sessions = await session_service.list_sessions(
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        skip=skip,
        limit=limit,
        agent_id=agent_id,
    )
    return [SessionResponse.model_validate(s) for s in sessions]


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate,
    current_user: AuthUser,
    session_service: SessionUseCase = Depends(get_session_service),
) -> SessionResponse:
    """创建新会话"""
    user_id, anonymous_user_id = _get_user_ids(current_user)
    try:
        session = await session_service.create_session(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            agent_id=data.agent_id,
            title=data.title,
        )
    except IntegrityError as e:
        # 捕获外键约束错误（如无效agent_id?        await session_service.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent_id or other constraint violation",
        ) from e
    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionUseCase = Depends(get_session_service),
) -> SessionResponse:
    """获取会话详情"""
    session = await session_service.get_session_or_raise(session_id)
    check_session_ownership(session, current_user)
    return SessionResponse.model_validate(session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    data: SessionUpdate,
    current_user: AuthUser,
    session_service: SessionUseCase = Depends(get_session_service),
) -> SessionResponse:
    """更新会话"""
    session = await session_service.get_session_or_raise(session_id)
    check_session_ownership(session, current_user)

    # Check which fields were explicitly set (including None)
    # Use model_dump(exclude_unset=True) to see what was provided
    provided_fields = data.model_dump(exclude_unset=True)

    # Pass ... for fields that weren't provided, and the actual value (including None) for fields that were
    title = provided_fields.get("title", ...)
    status = provided_fields.get("status", ...)

    updated_session = await session_service.update_session(
        session_id=session_id,
        title=title,
        status=status,
    )
    return SessionResponse.model_validate(updated_session)


@router.post("/{session_id}/generate-title", response_model=SessionResponse)
async def generate_session_title(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionUseCase = Depends(get_session_service),
    title_service: TitleUseCase = Depends(get_title_service),
    strategy: Annotated[str, Query(description="生成策略: first_message 或 summary")] = "summary",
) -> SessionResponse:
    """生成会话标题"""
    session = await session_service.get_session_or_raise(session_id)
    check_session_ownership(session, current_user)

    if strategy not in ["first_message", "summary"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid strategy. Must be 'first_message' or 'summary'",
        )

    first_message = None
    if strategy == "first_message":
        messages = await session_service.get_messages(session_id, skip=0, limit=1)
        if messages and messages[0].content:
            first_message = messages[0].content

    success = await title_service.generate_and_update(
        session_id=session_id,
        strategy=strategy,  # type: ignore
        message=first_message,
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate title",
        )

    await session_service.db.refresh(session)
    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionUseCase = Depends(get_session_service),
) -> None:
    """删除会话"""
    session = await session_service.get_session_or_raise(session_id)
    check_session_ownership(session, current_user)
    await session_service.delete_session(session_id)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionUseCase = Depends(get_session_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MessageResponse]:
    """获取会话的消息历史"""
    session = await session_service.get_session_or_raise(session_id)
    check_session_ownership(session, current_user)

    messages = await session_service.get_messages(session_id, skip=skip, limit=limit)
    result = []
    for msg in messages:
        msg_dict = {
            "id": str(msg.id),
            "session_id": str(msg.session_id),
            "role": msg.role,
            "content": msg.content,
            "tool_calls": dict(msg.tool_calls) if msg.tool_calls else None,
            "tool_call_id": msg.tool_call_id,
            "metadata": dict(msg.extra_data)
            if hasattr(msg, "extra_data") and msg.extra_data
            else {},
            "token_count": msg.token_count,
            "created_at": msg.created_at,
        }
        result.append(MessageResponse.model_validate(msg_dict))
    return result
