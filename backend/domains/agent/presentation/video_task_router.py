"""
Video Task API - 视频生成任务接口
"""

from datetime import datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from domains.agent.application.video_task_use_case import VideoTaskUseCase
from domains.identity.domain.types import Principal
from domains.identity.presentation.deps import AuthUser
from libs.api.deps import get_video_task_service

router = APIRouter()


def _get_user_ids(
    current_user: AuthUser,
) -> tuple[uuid.UUID | None, str | None, int | None]:
    """从当前用户获取 user_id、anonymous_user_id 和 vendor_creator_id

    Returns:
        (user_id, anonymous_user_id, vendor_creator_id) 元组
    """
    if current_user.is_anonymous:
        return None, Principal.extract_anonymous_id(current_user.id), None
    return uuid.UUID(current_user.id), None, current_user.vendor_creator_id


# =============================================================================
# Request/Response Schemas
# =============================================================================


class VideoTaskCreate(BaseModel):
    """创建视频任务请求"""

    model_config = ConfigDict(strict=True)

    session_id: str | None = Field(default=None, description="关联会话ID")
    prompt_text: str | None = Field(default=None, max_length=2000, description="视频生成提示词")
    prompt_source: str | None = Field(default=None, description="提示词来源")
    reference_images: list[str] = Field(default_factory=list, description="参考图片URL列表")
    marketplace: str = Field(default="jp", description="目标站点")
    model: str = Field(
        default="openai::sora1.0", description="视频生成模型: openai::sora1.0, openai::sora2.0"
    )
    duration: int = Field(
        default=5, description="视频时长（秒）: sora1支持5/10/15/20, sora2支持5/10/15"
    )
    auto_submit: bool = Field(default=False, description="是否自动提交到厂商")


class VideoTaskUpdate(BaseModel):
    """更新视频任务请求"""

    prompt_text: str | None = None
    prompt_source: str | None = None
    reference_images: list[str] | None = None
    marketplace: str | None = None
    model: str | None = None
    duration: int | None = None


class VideoTaskResponse(BaseModel):
    """视频任务响应"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str | None
    anonymous_user_id: str | None
    session_id: str | None
    workflow_id: str | None
    run_id: str | None
    status: str
    prompt_text: str | None
    prompt_source: str | None
    reference_images: list[str]
    marketplace: str
    model: str
    duration: int
    result: dict | None
    error_message: str | None
    video_url: str | None
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "user_id", "session_id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: uuid.UUID | str | None) -> str | None:
        """将 UUID 转换为字符串"""
        if v is None:
            return None
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime(cls, v: datetime | str | None) -> datetime | None:
        """将字符串转换为 datetime"""
        if v is None:
            return None
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v


class VideoTaskListResponse(BaseModel):
    """视频任务列表响应"""

    items: list[VideoTaskResponse]
    total: int
    skip: int
    limit: int


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/", response_model=VideoTaskListResponse)
async def list_video_tasks(
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    task_status: Annotated[str | None, Query(alias="status")] = None,
    session_id: Annotated[str | None, Query(description="按会话筛选")] = None,
) -> VideoTaskListResponse:
    """获取用户的视频任务列表"""
    session_uuid = None
    if session_id:
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Invalid session_id: {session_id}") from e

    tasks, total = await video_task_service.list_tasks(
        skip=skip,
        limit=limit,
        status=task_status,
        session_id=session_uuid,
    )
    return VideoTaskListResponse(
        items=[VideoTaskResponse.model_validate(t) for t in tasks],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=VideoTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_video_task(
    data: VideoTaskCreate,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
) -> VideoTaskResponse:
    """创建视频生成任务"""
    _, _, vendor_creator_id = _get_user_ids(current_user)

    session_id = None
    if data.session_id:
        try:
            session_id = uuid.UUID(data.session_id)
        except ValueError as e:
            raise HTTPException(
                status_code=422, detail=f"Invalid session_id: {data.session_id}"
            ) from e

    task = await video_task_service.create_task(
        principal_id=current_user.id,
        session_id=session_id,
        prompt_text=data.prompt_text,
        prompt_source=data.prompt_source,
        reference_images=data.reference_images,
        marketplace=data.marketplace,
        model=data.model,
        duration=data.duration,
        auto_submit=data.auto_submit,
        vendor_creator_id=vendor_creator_id,
    )
    return VideoTaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=VideoTaskResponse)
async def get_video_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
) -> VideoTaskResponse:
    """获取视频任务详情"""
    task = await video_task_service.get_task(task_id)
    return VideoTaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=VideoTaskResponse)
async def update_video_task(
    task_id: uuid.UUID,
    data: VideoTaskUpdate,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
) -> VideoTaskResponse:
    """更新视频任务"""
    provided_fields = data.model_dump(exclude_unset=True)
    task = await video_task_service.update_task(
        task_id=task_id,
        **provided_fields,
    )
    return VideoTaskResponse.model_validate(task)


@router.post("/{task_id}/submit", response_model=VideoTaskResponse)
async def submit_video_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
) -> VideoTaskResponse:
    """提交视频任务到厂商"""
    task = await video_task_service.submit_task(task_id)
    return VideoTaskResponse.model_validate(task)


@router.post("/{task_id}/poll", response_model=VideoTaskResponse)
async def poll_video_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
    once: bool = Query(default=False, description="是否单次查询"),
) -> VideoTaskResponse:
    """轮询视频任务状态"""
    task = await video_task_service.poll_task(task_id, once=once)
    return VideoTaskResponse.model_validate(task)


@router.post("/{task_id}/cancel", response_model=VideoTaskResponse)
async def cancel_video_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
) -> VideoTaskResponse:
    """取消视频任务"""
    task = await video_task_service.cancel_task(task_id)
    return VideoTaskResponse.model_validate(task)


@router.post("/{task_id}/retry", response_model=VideoTaskResponse)
async def retry_video_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
) -> VideoTaskResponse:
    """重试失败或已取消的视频任务

    将任务重置为 pending 状态并重新提交到厂商。
    仅支持 failed 或 cancelled 状态的任务。
    """
    task = await video_task_service.retry_task(task_id)
    return VideoTaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video_task(
    task_id: uuid.UUID,
    current_user: AuthUser,
    video_task_service: VideoTaskUseCase = Depends(get_video_task_service),
) -> None:
    """删除视频任务（仅支持 pending 状态的任务）"""
    task = await video_task_service.get_task(task_id)
    if task["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能删除待提交状态的任务",
        )
    await video_task_service.cancel_task(task_id)
