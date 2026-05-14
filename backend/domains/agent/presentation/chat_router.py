"""
Chat API - 对话 API

实现:
- POST /chat: 发送消(SSE 流式响应)
- POST /chat/resume: 恢复执行
- GET /chat/checkpoints/{session_id}: 获取检查点列表
- GET /chat/checkpoints/{checkpoint_id}/state: 获取检查点状- POST /chat/checkpoints/diff: 对比检查点
"""

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application import ChatUseCase
from domains.agent.application.checkpoint_service import CheckpointService
from domains.agent.application.user_model_use_case import UserModelUseCase
from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter
from domains.identity.presentation.deps import AuthUser
from domains.session.application import SessionUseCase
from domains.tenancy.presentation.team_dependencies import AttachOptionalTeamContext
from libs.api.deps import get_checkpoint_service, get_sandbox_service
from libs.db.database import get_session_context
from libs.db.permission_context import (
    PermissionContext,
    get_permission_context,
    set_permission_context,
)
from utils.serialization import Serializer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


def _build_stream_chat_service(db: AsyncSession, request: Request) -> ChatUseCase:
    """为 SSE 生成器创建独立 ChatUseCase，避免复用 FastAPI 依赖 session。"""
    sandbox_service = get_sandbox_service(request)
    session_service = SessionUseCase(db, sandbox_service=sandbox_service)
    checkpointer = getattr(request.app.state, "checkpointer", None)
    catalog = get_model_catalog_adapter(db)
    user_models = UserModelUseCase(db, catalog=catalog)
    return ChatUseCase(
        db,
        session_use_case=session_service,
        session_use_case_factory=SessionUseCase,
        checkpointer=checkpointer,
        model_catalog=catalog,
        user_model_use_case=user_models,
    )


# =============================================================================
# Request/Response Schemas
# =============================================================================


class MCPConfigInput(BaseModel):
    """MCP 配置（仅新会话生效）"""

    enabled_servers: list[str] = Field(
        default_factory=list, description="启用的 MCP 服务器 ID 列表"
    )


class ChatRequest(BaseModel):
    """对话请求"""

    model_config = ConfigDict(strict=True)

    message: str = Field(..., min_length=1, description="用户消息")
    session_id: str | None = Field(default=None, description="会话 ID（可选）")
    agent_id: str | None = Field(default=None, description="Agent ID（可选）")
    mcp_config: MCPConfigInput | None = Field(default=None, description="MCP 配置（仅新会话生效）")
    model_ref: str | None = Field(
        default=None,
        max_length=300,
        description="系统模型 id（如 provider/model）或用户模型 UUID；省略则使用会话已存或 Agent 默认",
    )
    gateway_verbose_request_log: bool | None = Field(
        default=None,
        description="True 且服务端允许时本请求启用网关详细日志（仍截断）；None=仅会话/vkey",
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str | None) -> str | None:
        """验证 session_id：如果提供，不能为空字符串"""
        if v is not None and v == "":
            raise ValueError("session_id cannot be empty string")
        return v


class ResumeRequest(BaseModel):
    """恢复执行请求"""

    model_config = ConfigDict(strict=True)

    session_id: str
    checkpoint_id: str
    action: str = Field(..., pattern="^(approve|reject|modify)$")
    modified_args: dict[str, Any] | None = None


class DiffRequest(BaseModel):
    """检查点对比请求"""

    model_config = ConfigDict(strict=True)

    checkpoint_id_1: str
    checkpoint_id_2: str


class CheckpointItem(BaseModel):
    """检查点列表项"""

    id: str
    session_id: str
    step: int
    created_at: str
    parent_id: str | None


class DiffResponse(BaseModel):
    """检查点对比响应"""

    messages_added: int
    tokens_delta: int
    iteration_delta: int
    new_messages: list[dict[str, Any]]


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("")
async def chat(
    request: ChatRequest,
    http_request: Request,
    _: AttachOptionalTeamContext,
    current_user: AuthUser,
) -> StreamingResponse:
    """
    发送消息并获取流式响应

    使用 Server-Sent Events (SSE) 返回事件流
    """

    permission_context = get_permission_context()

    async def event_generator():
        try:
            if isinstance(permission_context, PermissionContext):
                set_permission_context(permission_context)
            async with get_session_context() as db:
                chat_service = _build_stream_chat_service(db, http_request)
                mcp_config_dict = (
                    {"enabled_servers": request.mcp_config.enabled_servers}
                    if request.mcp_config
                    else None
                )
                async for event in chat_service.chat(
                    session_id=request.session_id,
                    message=request.message,
                    agent_id=request.agent_id,
                    user_id=current_user.id,
                    mcp_config=mcp_config_dict,
                    model_ref=request.model_ref,
                    gateway_verbose_request_log=request.gateway_verbose_request_log,
                ):
                    try:
                        event_dict = event.model_dump(mode="json", warnings="error")
                    except Exception:
                        logger.error("⚠️ Pydantic 序列化错误！完整堆栈", exc_info=True)
                        event_dict = Serializer.serialize_dict(event.model_dump())
                    serialized_data = Serializer.serialize(event_dict)
                    yield f"data: {json.dumps(serialized_data)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            error_data = {"type": "error", "data": {"error": str(e)}}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/resume")
async def resume_execution(
    request: ResumeRequest,
    http_request: Request,
    _: AttachOptionalTeamContext,
    current_user: AuthUser,
) -> StreamingResponse:
    """
    恢复中断的执行

    用于 Human-in-the-Loop 场景
    """

    permission_context = get_permission_context()

    async def event_generator():
        try:
            if isinstance(permission_context, PermissionContext):
                set_permission_context(permission_context)
            async with get_session_context() as db:
                chat_service = _build_stream_chat_service(db, http_request)
                async for event in chat_service.resume(
                    session_id=request.session_id,
                    checkpoint_id=request.checkpoint_id,
                    action=request.action,
                    modified_args=request.modified_args,
                    user_id=current_user.id,
                ):
                    event_dict = event.model_dump(mode="json")
                    serialized_data = Serializer.serialize(event_dict)
                    yield f"data: {json.dumps(serialized_data)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            error_data = {"type": "error", "data": {"error": str(e)}}
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/checkpoints/{session_id}", response_model=list[CheckpointItem])
async def list_checkpoints(
    session_id: str,
    current_user: AuthUser,
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[CheckpointItem]:
    """获取会话的检查点列表"""
    checkpoints = await checkpoint_service.list_history(session_id, limit)
    return [
        CheckpointItem(
            id=cp.id,
            session_id=cp.session_id,
            step=cp.step,
            created_at=cp.created_at.isoformat(),
            parent_id=cp.parent_id,
        )
        for cp in checkpoints
    ]


@router.get("/checkpoints/{checkpoint_id}/state")
async def get_checkpoint_state(
    checkpoint_id: str,
    current_user: AuthUser,
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
) -> dict[str, Any]:
    """获取检查点状态"""
    checkpoint = await checkpoint_service.get_or_raise(checkpoint_id)
    state_dict = checkpoint.state.model_dump(mode="json")
    return Serializer.serialize(state_dict)  # type: ignore[return-value]


@router.post("/checkpoints/diff", response_model=DiffResponse)
async def diff_checkpoints(
    request: DiffRequest,
    current_user: AuthUser,
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
) -> DiffResponse:
    """对比两个检查点"""
    result = await checkpoint_service.diff(
        request.checkpoint_id_1,
        request.checkpoint_id_2,
    )
    return DiffResponse(**result)
