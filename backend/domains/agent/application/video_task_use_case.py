"""
Video Task Use Case - 视频生成任务用例

提供视频生成任务的业务逻辑：创建、查询、更新、轮询等。
视频生成经 Gateway 代理（``GatewayProxyProtocol.video_generation``），与对话/生图
统一计费与归因；执行为同步阻塞调用，通过后台 ``asyncio`` task 等待完成，前端轮询
只读 DB 状态。

会话创建与所有权校验统一通过 SessionUseCase，不直接依赖 Session 的 Infrastructure。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.application.video_gen_catalog import (
    allowed_durations_for_video_model,
    list_merged_video_models,
)
from domains.agent.domain.services.title_rules import is_default_title
from domains.agent.domain.types import MessageRole
from domains.agent.infrastructure.models.video_gen_task import VideoGenTask, VideoGenTaskStatus
from domains.agent.infrastructure.repositories.video_gen_task_repository import (
    VideoGenTaskRepository,
)
from domains.gateway.application.billing_context import resolve_billing_context
from domains.gateway.application.gateway_proxy_factory import get_gateway_proxy
from domains.gateway.application.ports import GatewayCallContext
from domains.session.application.ports import SessionApplicationPort
from libs.db.database import get_session_context
from libs.exceptions import NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

# 视频任务会话默认标题（新建且无 prompt 时使用）
VIDEO_SESSION_DEFAULT_TITLE = "视频生成"

# 后台 task 引用持有，避免被 GC 回收（任务完成时移除）。
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


async def _ensure_session_title(
    session_use_case: SessionApplicationPort,
    session_id: str,
    current_title: str | None,
    *,
    is_new: bool,
    prompt_text: str | None,
) -> None:
    """在创建视频任务时补全会话标题，避免侧栏一直显示「新对话」。

    - 已有会话且无/默认标题且有 prompt_text：用 prompt 前 50 字作为标题。
    - 新建会话且无标题（如 prompt 为空）：设为「视频生成」。
    """
    if not session_id:
        return
    if is_new:
        if not current_title or not current_title.strip():
            await session_use_case.update_session(session_id, title=VIDEO_SESSION_DEFAULT_TITLE)
        return
    if not prompt_text or not prompt_text.strip():
        return
    if current_title and not is_default_title(current_title):
        return
    title = prompt_text[:50] + ("..." if len(prompt_text) > 50 else "")
    await session_use_case.update_session(session_id, title=title)


def _extract_video_url(result: dict[str, Any]) -> str | None:
    """从 OpenAI 兼容 ``/v1/videos`` 响应提取视频 URL。"""
    video = result.get("video")
    if isinstance(video, dict):
        url = video.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    url = result.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    content = result.get("content")
    if isinstance(content, dict):
        content_url = content.get("video_url")
        if isinstance(content_url, str) and content_url.strip():
            return content_url.strip()
    return None


def _is_volcengine_video_still_processing(result: dict[str, Any]) -> bool:
    """响应仅有任务 id/status、尚无视频 URL 时视为仍在生成（不应立即标 failed）。"""
    if _extract_video_url(result):
        return False
    status = result.get("status")
    if not isinstance(status, str):
        return False
    return status.strip().lower() in {"queued", "running", "processing", "pending"}


async def _run_generation_background(
    task_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    team_id: uuid.UUID | None,
    prompt: str,
    model: str,
    duration: int,
    reference_images: list[str],
) -> None:
    """后台执行视频生成：调用 Gateway ``video_generation`` 并回写任务状态。

    LiteLLM ``avideo_generation`` 为同步阻塞调用（默认 600s），在此后台 task 中
    等待完成后将结果写入 DB；前端通过 ``poll_task`` 只读 DB 状态。
    """
    async with get_session_context() as session:
        repo = VideoGenTaskRepository(session)
        if await repo.get_status_by_id(task_id) == VideoGenTaskStatus.CANCELLED:
            return
        await repo.update_by_id(
            task_id,
            {"status": VideoGenTaskStatus.RUNNING, "error_message": None},
        )
        await session.commit()

        if await repo.get_status_by_id(task_id) == VideoGenTaskStatus.CANCELLED:
            return

        ctx = GatewayCallContext(
            user_id=user_id,
            team_id=team_id,
            capability="video_generation",
            metadata={"video_task_id": str(task_id)},
        )
        try:
            result = await get_gateway_proxy().video_generation(
                prompt=prompt,
                ctx=ctx,
                model=model,
                seconds=duration,
                reference_image_urls=reference_images or None,
            )
        except Exception as exc:
            logger.error("video generation failed for task %s: %s", task_id, exc)
            if await repo.get_status_by_id(task_id) == VideoGenTaskStatus.CANCELLED:
                return
            await repo.update_by_id(
                task_id,
                {
                    "status": VideoGenTaskStatus.FAILED,
                    "error_message": str(exc) or "视频生成调用失败",
                },
            )
            await session.commit()
            return

        if await repo.get_status_by_id(task_id) == VideoGenTaskStatus.CANCELLED:
            return

        if not isinstance(result, dict):
            result = {}

        video_url = _extract_video_url(result)
        vendor_task_id = result.get("id")
        workflow_id = str(vendor_task_id) if isinstance(vendor_task_id, str) and vendor_task_id else None
        if video_url:
            await repo.update_by_id(
                task_id,
                {
                    "status": VideoGenTaskStatus.COMPLETED,
                    "result": result,
                    "workflow_id": workflow_id,
                    "error_message": None,
                },
            )
            logger.info("video task %s completed: video_url=%s", task_id, video_url[:80])
        elif _is_volcengine_video_still_processing(result):
            await repo.update_by_id(
                task_id,
                {
                    "status": VideoGenTaskStatus.RUNNING,
                    "result": result,
                    "workflow_id": workflow_id,
                    "error_message": None,
                },
            )
            logger.warning(
                "video task %s still processing upstream (status=%s)",
                task_id,
                result.get("status"),
            )
        else:
            await repo.update_by_id(
                task_id,
                {
                    "status": VideoGenTaskStatus.FAILED,
                    "error_message": "视频生成完成但未返回视频文件，请重试",
                    "result": result,
                    "workflow_id": workflow_id,
                },
            )
            logger.warning("video task %s marked failed: no video_url in result", task_id)
        await session.commit()


def _spawn_background_generation(
    task_id: uuid.UUID,
    *,
    user_id: uuid.UUID,
    team_id: uuid.UUID | None,
    prompt: str,
    model: str,
    duration: int,
    reference_images: list[str],
) -> None:
    """启动后台视频生成 task 并注册引用，避免被 GC 回收。"""
    coro = _run_generation_background(
        task_id,
        user_id=user_id,
        team_id=team_id,
        prompt=prompt,
        model=model,
        duration=duration,
        reference_images=reference_images,
    )
    task = asyncio.create_task(coro, name=f"video-gen-{task_id}")
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


class VideoTaskUseCase:
    """视频生成任务用例"""

    def __init__(
        self,
        db: AsyncSession,
        session_use_case: SessionApplicationPort,
    ) -> None:
        self.db = db
        self.repo = VideoGenTaskRepository(db)
        self.session_use_case = session_use_case

    async def list_tasks(
        self,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
        session_id: uuid.UUID | None = None,
        prompt_source: str | None = None,
    ) -> tuple[list[dict], int]:
        """列出当前用户的视频生成任务"""
        filters: dict = {}
        if status:
            filters["status"] = status
        if session_id:
            filters["session_id"] = session_id
        if prompt_source:
            filters["prompt_source"] = prompt_source

        tasks = await self.repo.find_for_tenants(
            skip=skip,
            limit=limit,
            order_by="created_at",
            order_desc=True,
            **filters,
        )
        total = await self.repo.count_for_tenants(**filters)

        return [self._to_dict(t) for t in tasks], total

    async def get_task(self, task_id: uuid.UUID) -> dict:
        """获取单个任务（自动检查所有权）"""
        task = await self.repo.get_in_tenants(task_id)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))
        return self._to_dict(task)

    async def create_task(
        self,
        principal_id: str,
        session_id: uuid.UUID | None = None,
        prompt_text: str | None = None,
        prompt_source: str | None = None,
        reference_images: list[str] | None = None,
        marketplace: str = "jp",
        model: str | None = None,
        duration: int = 5,
        auto_submit: bool = False,
        auto_create_session: bool = True,
        catalog_user_id: uuid.UUID | None = None,
    ) -> dict:
        """创建视频生成任务

        Args:
            principal_id: 当前用户 Principal ID（与 Chat 一致，含 anonymous- 前缀时表示匿名）
            session_id: 关联会话 ID（如果未提供且 auto_create_session=True，将自动创建；若提供则校验所有权）
            prompt_text: 视频生成提示词
            prompt_source: 提示词来源
            reference_images: 参考图片 URL 列表
            marketplace: 目标站点
            model: 视频生成模型（网关 ``model_type=video`` 的模型 ID）；为空时取可见目录首个
            duration: 视频时长（秒）
            auto_submit: 是否自动提交到 Gateway 执行
            auto_create_session: 如果未提供 session_id，是否自动创建会话

        Raises:
            ValidationError: 参数验证失败
            PermissionDeniedError: 提供的 session_id 不属于当前用户
        """
        if not principal_id or not principal_id.strip():
            raise ValidationError(
                "principal_id is required",
                code="MISSING_OWNER",
            )

        # 验证 marketplace
        valid_marketplaces = {"jp", "us", "de", "uk", "fr", "it", "es"}
        if marketplace not in valid_marketplaces:
            raise ValidationError(
                f"Invalid marketplace: {marketplace}. Valid values: {valid_marketplaces}",
                code="INVALID_MARKETPLACE",
            )

        merged_catalog = await list_merged_video_models(self.db, user_id=catalog_user_id)
        valid_ids = frozenset(str(x["value"]) for x in merged_catalog)
        if model is None or not str(model).strip():
            if not valid_ids:
                raise ValidationError(
                    "当前没有可用的视频生成模型，请先在 Gateway 配置 model_type=video 的模型",
                    code="NO_VIDEO_MODEL",
                )
            model = next(iter(sorted(valid_ids)))
        model = str(model).strip()
        if model not in valid_ids:
            raise ValidationError(
                f"Invalid model: {model}. Valid values: {sorted(valid_ids)}",
                code="INVALID_MODEL",
            )

        valid_durations = allowed_durations_for_video_model(merged_catalog, model)
        if duration not in valid_durations:
            raise ValidationError(
                f"Invalid duration for {model}: {duration}. Valid values: {sorted(valid_durations)}",
                code="INVALID_DURATION",
            )

        # 解析会话：复用 Session 域统一入口（有 session_id 则校验所有权，无则按需创建）
        actual_session_id: uuid.UUID | None = None
        if session_id or auto_create_session:
            default_title = None
            if not session_id and prompt_text:
                default_title = prompt_text[:50] + ("..." if len(prompt_text) > 50 else "")
            session, is_new = await self.session_use_case.get_or_create_session_for_principal(
                principal_id=principal_id,
                session_id=str(session_id) if session_id else None,
                title=default_title,
            )
            actual_session_id = session.id
            if is_new:
                logger.info("Auto-created session %s for video task", actual_session_id)

            if actual_session_id:
                await _ensure_session_title(
                    self.session_use_case,
                    str(actual_session_id),
                    session.title,
                    is_new=is_new,
                    prompt_text=prompt_text,
                )

        task = await self.repo.create(
            session_id=actual_session_id,
            prompt_text=prompt_text,
            prompt_source=prompt_source,
            reference_images=reference_images,
            marketplace=marketplace,
            model=model,
            duration=duration,
        )

        if actual_session_id:
            await self.session_use_case.increment_video_task_count(str(actual_session_id))

        if prompt_text and actual_session_id:
            await self.session_use_case.add_message(
                session_id=str(actual_session_id),
                role=MessageRole.USER,
                content=prompt_text,
                metadata={"source": "video_task", "task_id": str(task.id)},
            )

        await self.db.commit()

        if auto_submit and prompt_text:
            await self._spawn_generation(task)

        return self._to_dict(task)

    async def update_task(
        self,
        task_id: uuid.UUID,
        **kwargs: Any,
    ) -> dict:
        """更新任务"""
        task = await self.repo.update_fields(task_id, **kwargs)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        await self.db.commit()
        return self._to_dict(task)

    async def submit_task(self, task_id: uuid.UUID) -> dict:
        """提交任务到 Gateway 执行（启动后台生成 task）

        Raises:
            NotFoundError: 任务不存在或无权限
            ValidationError: 任务状态不允许提交
        """
        task = await self.repo.get_in_tenants(task_id)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        if task.status != VideoGenTaskStatus.PENDING:
            raise ValidationError(
                f"Cannot submit task in status: {task.status}",
                code="INVALID_TASK_STATUS",
            )

        if not task.prompt_text:
            raise ValidationError(
                "Cannot submit task without prompt_text",
                code="MISSING_PROMPT",
            )

        await self._spawn_generation(task)
        await self.db.commit()
        return self._to_dict(task)

    async def poll_task(self, task_id: uuid.UUID, once: bool = False) -> dict:
        """轮询任务状态（只读 DB；后台 task 完成后自动写入终态）

        Args:
            once: 兼容旧参数，现仅返回当前 DB 状态
        """
        _ = once
        return await self.get_task(task_id)

    async def cancel_task(self, task_id: uuid.UUID) -> dict:
        """取消任务

        注意：后台 task 无法真正中断上游视频生成，仅将任务标记为 CANCELLED；
        后台写入前会检查该状态，避免覆盖已取消任务。
        """
        task = await self.repo.get_in_tenants(task_id)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        if task.status not in (VideoGenTaskStatus.PENDING, VideoGenTaskStatus.RUNNING):
            raise ValidationError(
                f"Cannot cancel task in status: {task.status}",
                code="INVALID_TASK_STATUS",
            )

        task = await self.repo.update_fields(
            task_id,
            status=VideoGenTaskStatus.CANCELLED,
        )
        await self.db.commit()
        return self._to_dict(task)  # type: ignore

    async def retry_task(self, task_id: uuid.UUID) -> dict:
        """重试失败或已取消的任务

        将任务重置为 pending 状态，清空结果字段后重新提交到 Gateway。

        Raises:
            NotFoundError: 任务不存在或无权限
            ValidationError: 任务状态不允许重试
        """
        task = await self.repo.get_in_tenants(task_id)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        if task.status not in (VideoGenTaskStatus.FAILED, VideoGenTaskStatus.CANCELLED):
            raise ValidationError(
                f"Cannot retry task in status: {task.status}. Only failed or cancelled tasks can be retried.",
                code="INVALID_TASK_STATUS",
            )

        if not task.prompt_text:
            raise ValidationError(
                "Cannot retry task without prompt_text",
                code="MISSING_PROMPT",
            )

        # 重置任务状态和结果字段
        task.status = VideoGenTaskStatus.PENDING
        task.workflow_id = None
        task.run_id = None
        task.result = None
        task.error_message = None
        await self.db.flush()

        await self._spawn_generation(task)
        await self.db.commit()

        logger.info("Task %s retried successfully, new status: %s", task_id, task.status)
        return self._to_dict(task)

    async def _spawn_generation(self, task: VideoGenTask) -> None:
        """解析计费上下文并启动后台视频生成 task。

        必须在请求上下文内调用（依赖 PermissionContext 解析 user_id/team_id）。
        """
        billing = await resolve_billing_context(self.db)
        if billing.user_id is None:
            raise ValidationError(
                "视频生成需要登录用户，无法解析当前用户身份",
                code="REQUIRES_AUTH",
            )
        if not task.prompt_text:
            raise ValidationError(
                "Cannot generate video without prompt_text",
                code="MISSING_PROMPT",
            )
        _spawn_background_generation(
            task.id,
            user_id=billing.user_id,
            team_id=billing.team_id,
            prompt=task.prompt_text,
            model=task.model,
            duration=task.duration,
            reference_images=list(task.reference_images or []),
        )

    def _to_dict(self, task: VideoGenTask) -> dict:
        """将任务转换为字典"""
        return {
            "id": str(task.id),
            "tenant_id": str(task.tenant_id),
            "session_id": str(task.session_id) if task.session_id else None,
            "workflow_id": task.workflow_id,
            "run_id": task.run_id,
            "status": task.status,
            "prompt_text": task.prompt_text,
            "prompt_source": task.prompt_source,
            "reference_images": task.reference_images,
            "marketplace": task.marketplace,
            "model": task.model,
            "duration": task.duration,
            "result": task.result,
            "error_message": task.error_message,
            "video_url": task.video_url,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        }
