"""Video Gen Task Repository - 视频生成任务仓储"""

from typing import Any
import uuid

from sqlalchemy import update

from domains.agent.infrastructure.models.video_gen_task import VideoGenTask
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.db.tenant_resolve import resolve_tenant_id_for_write


class VideoGenTaskRepository(TenantScopedRepositoryBase[VideoGenTask]):
    @property
    def model_class(self) -> type[VideoGenTask]:
        return VideoGenTask

    async def create(
        self,
        *,
        session_id: uuid.UUID | None = None,
        prompt_text: str | None = None,
        prompt_source: str | None = None,
        reference_images: list[str] | None = None,
        marketplace: str = "jp",
        model: str = "openai::sora1.0",
        duration: int = 5,
        tenant_id: uuid.UUID | None = None,
    ) -> VideoGenTask:
        resolved = tenant_id or await resolve_tenant_id_for_write(self.db)
        task = VideoGenTask(
            tenant_id=resolved,
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

    async def update_fields(self, task_id: uuid.UUID, **kwargs: Any) -> VideoGenTask | None:
        task = await self.get_in_tenants(task_id)
        if not task:
            return None
        for field, value in kwargs.items():
            if hasattr(task, field):
                setattr(task, field, value)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def update_by_id(self, task_id: uuid.UUID, values: dict[str, Any]) -> None:
        q = update(VideoGenTask).where(VideoGenTask.id == task_id).values(**values)
        await self.db.execute(q)
