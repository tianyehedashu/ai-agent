"""
Chat API - 对话 API

实现:
- POST /chat: 发送消息 (SSE 流式响应)
- POST /chat/resume: 恢复执行
- GET /chat/checkpoints/{session_id}: 获取检查点列表
- GET /chat/checkpoints/{checkpoint_id}/state: 获取检查点状态
- POST /chat/checkpoints/diff: 对比检查点
"""

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from api.deps import AuthUser, get_chat_service, get_checkpoint_service
from services.chat import ChatService
from services.checkpoint import CheckpointService

router = APIRouter(prefix="/chat", tags=["Chat"])


# =============================================================================
# Request/Response Schemas
# =============================================================================


class ChatRequest(BaseModel):
    """对话请求"""

    model_config = ConfigDict(strict=True)

    message: str = Field(..., min_length=1, description="用户消息")
    session_id: str | None = Field(default=None, description="会话 ID（可选）")
    agent_id: str | None = Field(default=None, description="Agent ID（可选）")


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
    current_user: AuthUser,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """
    发送消息并获取流式响应

    使用 Server-Sent Events (SSE) 返回事件流
    """

    async def event_generator():
        try:
            async for event in chat_service.chat(
                session_id=request.session_id,
                message=request.message,
                agent_id=request.agent_id,
                user_id=current_user.id,
            ):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(data)}\n\n"

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
    current_user: AuthUser,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """
    恢复中断的执行

    用于 Human-in-the-Loop 场景
    """

    async def event_generator():
        try:
            async for event in chat_service.resume(
                session_id=request.session_id,
                checkpoint_id=request.checkpoint_id,
                action=request.action,
                modified_args=request.modified_args,
                user_id=current_user.id,
            ):
                data = event.model_dump(mode="json")
                yield f"data: {json.dumps(data)}\n\n"

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
    # get_or_raise 会在检查点不存在时抛出 CheckpointError
    checkpoint = await checkpoint_service.get_or_raise(checkpoint_id)
    return checkpoint.state.model_dump(mode="json")


@router.post("/checkpoints/diff", response_model=DiffResponse)
async def diff_checkpoints(
    request: DiffRequest,
    current_user: AuthUser,
    checkpoint_service: CheckpointService = Depends(get_checkpoint_service),
) -> DiffResponse:
    """对比两个检查点"""
    # diff 会在检查点不存在时抛出 CheckpointError
    result = await checkpoint_service.diff(
        request.checkpoint_id_1,
        request.checkpoint_id_2,
    )
    return DiffResponse(**result)
