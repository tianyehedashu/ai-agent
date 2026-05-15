"""
Video Task Use Case - 视频生成任务用例

提供视频生成任务的业务逻辑：创建、查询、更新、轮询等。
会话创建与所有权校验统一通过 SessionUseCase，不直接依赖 Session 的 Infrastructure。
"""

from typing import Any
import uuid

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
from domains.agent.infrastructure.video_api.client import VideoAPIClient
from domains.identity.domain.types import Principal
from domains.session.application.ports import SessionApplicationPort
from domains.session.domain.entities import SessionOwner
from libs.exceptions import NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)

# 视频任务会话默认标题（新建且无 prompt 时使用）
VIDEO_SESSION_DEFAULT_TITLE = "视频生成"


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
        """列出当前用户的视频生成任务

        Args:
            skip: 跳过记录数
            limit: 返回记录数
            status: 按状态过滤（可选）
            session_id: 按会话过滤（可选）
            prompt_source: 按提示词来源过滤（可选，精确匹配）

        Returns:
            (任务列表, 总数)
        """
        filters: dict = {}
        if status:
            filters["status"] = status
        if session_id:
            filters["session_id"] = session_id
        if prompt_source:
            filters["prompt_source"] = prompt_source

        tasks = await self.repo.find_owned(
            skip=skip,
            limit=limit,
            order_by="created_at",
            order_desc=True,
            **filters,
        )
        total = await self.repo.count_owned(**filters)

        return [self._to_dict(t) for t in tasks], total

    async def get_task(self, task_id: uuid.UUID) -> dict:
        """获取单个任务（自动检查所有权）

        Args:
            task_id: 任务 ID

        Returns:
            任务详情

        Raises:
            NotFoundError: 任务不存在或无权限
        """
        task = await self.repo.get_owned(task_id)
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
        model: str = "openai::sora1.0",
        duration: int = 5,
        auto_submit: bool = False,
        auto_create_session: bool = True,
        vendor_creator_id: int | None = None,
    ) -> dict:
        """创建视频生成任务

        Args:
            principal_id: 当前用户 Principal ID（与 Chat 一致，含 anonymous- 前缀时表示匿名）
            session_id: 关联会话 ID（如果未提供且 auto_create_session=True，将自动创建；若提供则校验所有权）
            prompt_text: 视频生成提示词
            prompt_source: 提示词来源
            reference_images: 参考图片 URL 列表
            marketplace: 目标站点
            model: 视频生成模型（厂商 ``config.model``，见合并目录 ``list_merged_video_models``）
            duration: 视频时长（秒）
            auto_submit: 是否自动提交到厂商
            auto_create_session: 如果未提供 session_id，是否自动创建会话
            vendor_creator_id: 厂商系统操作用户 ID（可选）

        Returns:
            创建的任务

        Raises:
            ValidationError: 参数验证失败
            PermissionDeniedError: 提供的 session_id 不属于当前用户
        """
        if not principal_id or not principal_id.strip():
            raise ValidationError(
                "principal_id is required",
                code="MISSING_OWNER",
            )

        owner = SessionOwner.from_principal_id(
            principal_id, Principal.is_anonymous_id(principal_id)
        )

        # 验证 marketplace
        valid_marketplaces = {"jp", "us", "de", "uk", "fr", "it", "es"}
        if marketplace not in valid_marketplaces:
            raise ValidationError(
                f"Invalid marketplace: {marketplace}. Valid values: {valid_marketplaces}",
                code="INVALID_MARKETPLACE",
            )

        merged_catalog = await list_merged_video_models(self.db)
        valid_ids = frozenset(str(x["value"]) for x in merged_catalog)
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

            # 补全会话标题，避免视频任务对话一直显示「新对话」
            if actual_session_id:
                await _ensure_session_title(
                    self.session_use_case,
                    str(actual_session_id),
                    session.title,
                    is_new=is_new,
                    prompt_text=prompt_text,
                )

        task = await self.repo.create(
            user_id=owner.user_id,
            anonymous_user_id=owner.anonymous_user_id,
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
            task = await self._submit_to_vendor(task, vendor_creator_id=vendor_creator_id)
            await self.db.commit()

        return self._to_dict(task)

    async def update_task(
        self,
        task_id: uuid.UUID,
        **kwargs: Any,
    ) -> dict:
        """更新任务

        Args:
            task_id: 任务 ID
            **kwargs: 要更新的字段

        Returns:
            更新后的任务

        Raises:
            NotFoundError: 任务不存在或无权限
        """
        task = await self.repo.update(task_id, **kwargs)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        await self.db.commit()
        return self._to_dict(task)

    async def submit_task(self, task_id: uuid.UUID) -> dict:
        """提交任务到厂商

        Args:
            task_id: 任务 ID

        Returns:
            更新后的任务

        Raises:
            NotFoundError: 任务不存在或无权限
            ValidationError: 任务状态不允许提交
        """
        task = await self.repo.get_owned(task_id)
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

        task = await self._submit_to_vendor(task)
        await self.db.commit()
        return self._to_dict(task)

    async def poll_task(self, task_id: uuid.UUID, once: bool = False) -> dict:
        """轮询任务状态

        Args:
            task_id: 任务 ID
            once: 是否单次查询

        Returns:
            更新后的任务

        Raises:
            NotFoundError: 任务不存在或无权限
            ValidationError: 任务状态不允许轮询
        """
        task = await self.repo.get_owned(task_id)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        # 如果任务已完成但 video_url 为空，尝试从 result 中提取
        if task.status == VideoGenTaskStatus.COMPLETED and not task.video_url and task.result:
            video_url = VideoAPIClient.extract_video_url(task.result)
            if video_url:
                task.video_url = video_url
                await self.db.commit()
                logger.info("Extracted video_url from existing result for task %s", task_id)
            else:
                # result 存在但无法提取 video_url，标记为失败
                task.status = VideoGenTaskStatus.FAILED
                task.error_message = "视频生成完成但未返回视频文件，请重试"
                await self.db.commit()
                logger.warning("Task %s marked as failed: no video_url in result", task_id)
            return self._to_dict(task)

        if task.status not in (VideoGenTaskStatus.RUNNING, VideoGenTaskStatus.PENDING):
            # 任务已完成或失败，直接返回当前状态
            return self._to_dict(task)

        if not task.workflow_id or not task.run_id:
            raise ValidationError(
                "Cannot poll task without workflow_id and run_id",
                code="MISSING_VENDOR_IDS",
            )

        task = await self._poll_vendor(task)
        await self.db.commit()
        return self._to_dict(task)

    async def cancel_task(self, task_id: uuid.UUID) -> dict:
        """取消任务

        Args:
            task_id: 任务 ID

        Returns:
            更新后的任务

        Raises:
            NotFoundError: 任务不存在或无权限
            ValidationError: 任务状态不允许取消
        """
        task = await self.repo.get_owned(task_id)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        if task.status not in (VideoGenTaskStatus.PENDING, VideoGenTaskStatus.RUNNING):
            raise ValidationError(
                f"Cannot cancel task in status: {task.status}",
                code="INVALID_TASK_STATUS",
            )

        task = await self.repo.update(
            task_id,
            status=VideoGenTaskStatus.CANCELLED,
        )
        await self.db.commit()
        return self._to_dict(task)  # type: ignore

    async def retry_task(self, task_id: uuid.UUID) -> dict:
        """重试失败或已取消的任务

        将任务重置为 pending 状态，清空厂商相关字段后重新提交。

        Args:
            task_id: 任务 ID

        Returns:
            更新后的任务

        Raises:
            NotFoundError: 任务不存在或无权限
            ValidationError: 任务状态不允许重试
        """
        task = await self.repo.get_owned(task_id)
        if not task:
            raise NotFoundError("VideoGenTask", str(task_id))

        # 仅允许 failed 或 cancelled 状态的任务重试
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

        # 重置任务状态和厂商相关字段
        task.status = VideoGenTaskStatus.PENDING
        task.workflow_id = None
        task.run_id = None
        task.result = None
        task.error_message = None
        task.video_url = None

        await self.db.flush()

        # 重新提交到厂商
        task = await self._submit_to_vendor(task)
        await self.db.commit()

        logger.info("Task %s retried successfully, new status: %s", task_id, task.status)
        return self._to_dict(task)

    async def _submit_to_vendor(
        self, task: VideoGenTask, vendor_creator_id: int | None = None
    ) -> VideoGenTask:
        """提交任务到厂商（内部方法），通过 VideoAPIClient 调用 GIIKIN API。"""
        try:
            client = VideoAPIClient()
            workflow_id, run_id = await client.submit(
                prompt=task.prompt_text or "",
                reference_images=task.reference_images or [],
                marketplace=task.marketplace,
                model=task.model,
                duration=task.duration,
                creator_id=vendor_creator_id,
            )

            task.workflow_id = workflow_id
            task.run_id = run_id
            task.status = VideoGenTaskStatus.RUNNING
        except ImportError:
            # 视频 API 客户端尚未实现，使用占位逻辑
            logger.warning("VideoAPIClient not implemented, using placeholder logic")
            task.workflow_id = f"placeholder-{task.id}"
            task.run_id = f"placeholder-run-{task.id}"
            task.status = VideoGenTaskStatus.RUNNING
        except Exception as e:
            logger.error(f"Failed to submit task to vendor: {e}")
            task.status = VideoGenTaskStatus.FAILED
            task.error_message = str(e)

        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def _poll_vendor(self, task: VideoGenTask) -> VideoGenTask:
        """轮询厂商状态（内部方法），通过 VideoAPIClient 查询 GIIKIN 工作流状态。"""
        try:
            client = VideoAPIClient()
            status, result = await client.poll(
                workflow_id=task.workflow_id or "",
                run_id=task.run_id or "",
            )
            logger.info(
                "Poll vendor result: task_id=%s, vendor_status=%d, result_keys=%s",
                task.id,
                status,
                list(result.keys()) if result else None,
            )

            # 根据厂商返回的状态更新任务（与 client 状态码常量一致）
            if status == VideoAPIClient.STATUS_COMPLETED:  # 2 完成
                task.result = result
                # 提取视频 URL
                video_url = VideoAPIClient.extract_video_url(result)
                logger.info(
                    "Task %s completed: extracted video_url=%s",
                    task.id,
                    video_url[:100] if video_url else None,
                )
                if video_url:
                    task.status = VideoGenTaskStatus.COMPLETED
                    task.error_message = None
                else:
                    # 厂商返回完成但没有视频 URL，视为失败
                    task.status = VideoGenTaskStatus.FAILED
                    task.error_message = "视频生成完成但未返回视频文件，请重试"
                    logger.warning(
                        "Video task %s marked as failed: no video_url in result: %s",
                        task.id,
                        result,
                    )
            elif status == VideoAPIClient.STATUS_FAILED or status < 0:  # 3 或负数 失败
                task.status = VideoGenTaskStatus.FAILED
                task.error_message = (
                    result.get("message")
                    or result.get("error_message")
                    or result.get("error")
                    or "Video generation failed"
                )
            elif status in (
                VideoAPIClient.STATUS_CANCELED,
                VideoAPIClient.STATUS_TERMINATED,
                VideoAPIClient.STATUS_TIMED_OUT,
            ):
                task.status = VideoGenTaskStatus.FAILED
                task.error_message = (
                    result.get("message") or result.get("error") or f"Status: {status}"
                )
            else:
                # 其他状态（如 RUNNING=1）保持 RUNNING
                logger.debug(
                    "Task %s still running: vendor_status=%d",
                    task.id,
                    status,
                )
        except ImportError:
            logger.warning("VideoAPIClient not implemented, keeping current status")
        except Exception as e:
            logger.error("Failed to poll task status: %s", e)
            task.status = VideoGenTaskStatus.FAILED
            task.error_message = str(e)

        await self.db.flush()
        await self.db.refresh(task)
        logger.info(
            "Poll complete: task_id=%s, final_status=%s, video_url=%s",
            task.id,
            task.status,
            task.video_url[:50] if task.video_url else None,
        )
        return task

    def _to_dict(self, task: VideoGenTask) -> dict:
        """将任务转换为字典"""
        return {
            "id": str(task.id),
            "user_id": str(task.user_id) if task.user_id else None,
            "anonymous_user_id": task.anonymous_user_id,
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
