"""
Video Gen Task Repository - 视频生成任务仓储

带所有权过滤的视频生成任务数据访问层。
"""

from typing import Any
import uuid

from domains.agent.infrastructure.models.video_gen_task import VideoGenTask
from libs.db.base_repository import OwnedRepositoryBase


class VideoGenTaskRepository(OwnedRepositoryBase[VideoGenTask]):
    """视频生成任务仓储

    继承 OwnedRepositoryBase 提供自动所有权过滤。
    """

    @property
    def model_class(self) -> type[VideoGenTask]:
        """返回模型类"""
        return VideoGenTask

    @property
    def anonymous_user_id_column(self) -> str:
        """匿名用户 ID 字段名"""
        return "anonymous_user_id"

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        session_id: uuid.UUID | None = None,
        prompt_text: str | None = None,
        prompt_source: str | None = None,
        reference_images: list[str] | None = None,
        marketplace: str = "jp",
        model: str = "openai::sora1.0",
        duration: int = 5,
    ) -> VideoGenTask:
        """创建视频生成任务

        Args:
            user_id: 注册用户 ID
            anonymous_user_id: 匿名用户 ID
            session_id: 关联会话 ID
            prompt_text: 视频生成提示词
            prompt_source: 提示词来源
            reference_images: 参考图片 URL 列表
            marketplace: 目标站点
            model: 视频生成模型
            duration: 视频时长（秒）

        Returns:
            创建的任务实体
        """
        task = VideoGenTask(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            session_id=session_id,
            prompt_text=prompt_text,
            prompt_source=prompt_source,
            reference_images=reference_images or [],
            marketplace=marketplace,
            model=model,
            duration=duration,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def update(
        self,
        task_id: uuid.UUID,
        **kwargs: Any,
    ) -> VideoGenTask | None:
        """更新任务（自动检查所有权）

        Args:
            task_id: 任务 ID
            **kwargs: 要更新的字段

        Returns:
            更新后的任务或 None（如果不存在或无权限）
        """
        task = await self.get_owned(task_id)
        if not task:
            return None

        # 可更新的字段
        allowed_fields = {
            "workflow_id",
            "run_id",
            "status",
            "prompt_text",
            "prompt_source",
            "reference_images",
            "marketplace",
            "model",
            "duration",
            "result",
            "error_message",
        }

        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(task, field, value)

        await self.db.flush()
        await self.db.refresh(task)
        return task
