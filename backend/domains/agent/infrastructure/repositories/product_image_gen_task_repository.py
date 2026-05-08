"""
Product Image Gen Task Repository - 产品 8 图生成任务仓储
"""

from typing import Any
import uuid

from domains.agent.infrastructure.models.product_image_gen_task import (
    ProductImageGenTask,
)
from libs.db.base_repository import OwnedRepositoryBase


class ProductImageGenTaskRepository(OwnedRepositoryBase[ProductImageGenTask]):
    @property
    def model_class(self) -> type[ProductImageGenTask]:
        return ProductImageGenTask

    @property
    def anonymous_user_id_column(self) -> str:
        return "anonymous_user_id"

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        job_id: uuid.UUID | None = None,
        prompts: list | None = None,
        status: str = "pending",
    ) -> ProductImageGenTask:
        task = ProductImageGenTask(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            job_id=job_id,
            prompts=prompts or [],
            status=status,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def update(
        self,
        task_id: uuid.UUID,
        **kwargs: Any,
    ) -> ProductImageGenTask | None:
        task = await self.get_owned(task_id)
        if not task:
            return None
        allowed = {"status", "result_images", "error_message"}
        for field, value in kwargs.items():
            if field in allowed:
                setattr(task, field, value)
        await self.db.flush()
        await self.db.refresh(task)
        return task
