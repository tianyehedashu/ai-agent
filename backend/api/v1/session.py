"""
Session API - 会话管理接口
"""

from datetime import datetime
import json
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.deps import AuthUser, check_ownership, get_session_service, get_title_service
from services.session import SessionService
from services.title import TitleService

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
        """将 JSONB 字段转换为字典

        SQLAlchemy 的 JSONB 字段可能返回特殊对象，需要转换为普通字典。
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        # 处理 SQLAlchemy JSONB 类型或其他特殊对象
        try:
            # 方法1: 尝试 JSON 序列化/反序列化
            json_str = json.dumps(v, default=str)
            return json.loads(json_str)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        # 方法2: 如果对象有 data 属性（某些 JSONB 包装器）
        if hasattr(v, "data"):
            data = v.data
            if isinstance(data, dict):
                return data
        # 方法3: 尝试转换为字典
        try:
            if hasattr(v, "__dict__") and v.__dict__:
                return dict(v.__dict__)
        except (TypeError, AttributeError):
            pass
        # 如果所有方法都失败，对于 metadata 返回空字典，对于 tool_calls 返回 None
        # 通过检查字段名来判断
        return {}


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


@router.post("/{session_id}/generate-title", response_model=SessionResponse)
async def generate_session_title(
    session_id: str,
    current_user: AuthUser,
    session_service: SessionService = Depends(get_session_service),
    title_service: TitleService = Depends(get_title_service),
    strategy: Annotated[str, Query(description="生成策略: first_message 或 summary")] = "summary",
) -> SessionResponse:
    """生成会话标题

    支持两种策略：
    - first_message: 根据第一条消息生成（仅当会话只有一条消息时有效）
    - summary: 根据多条消息总结生成
    """
    session = await session_service.get_by_id_or_raise(session_id)

    # 检查权限
    check_ownership(str(session.user_id), current_user.id, "Session")

    # 验证策略
    if strategy not in ["first_message", "summary"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid strategy. Must be 'first_message' or 'summary'",
        )

    # 获取第一条消息（如果是 first_message 策略）
    first_message = None
    if strategy == "first_message":
        messages = await session_service.get_messages(session_id, skip=0, limit=1)
        if messages and messages[0].content:
            first_message = messages[0].content

    # 生成并更新标题
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

    # 刷新会话并返回
    await session_service.db.refresh(session)
    return SessionResponse.model_validate(session)


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
    # 手动转换消息，确保 JSONB 字段正确序列化
    result = []
    for msg in messages:
        # 确保 metadata 和 tool_calls 是字典类型
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
