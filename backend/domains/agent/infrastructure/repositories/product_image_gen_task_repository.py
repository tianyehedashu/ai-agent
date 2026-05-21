"""Product Image Gen Task Repository"""

from typing import Any
import uuid

from domains.agent.infrastructure.models.product_image_gen_task import ProductImageGenTask
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.db.tenant_resolve import resolve_tenant_id_for_write


class ProductImageGenTaskRepository(TenantScopedRepositoryBase[ProductImageGenTask]):
    @property
    def model_class(self) -> type[ProductImageGenTask]:
        return ProductImageGenTask

    async def create(
        self,
        *,
        job_id: uuid.UUID | None = None,
        prompts: list | None = None,
        status: str = "pending",
        tenant_id: uuid.UUID | None = None,
    ) -> ProductImageGenTask:
        resolved = tenant_id or await resolve_tenant_id_for_write(self.db)
        task = ProductImageGenTask(
            tenant_id=resolved,
            job_id=job_id,
            prompts=prompts or [],
            status=status,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task

    async def update(self, task_id: uuid.UUID, **kwargs: Any) -> ProductImageGenTask | None:
        task = await self.get_in_tenants(task_id)
        if not task:
            return None
        allowed = {"status", "result_images", "error_message"}
        for field, value in kwargs.items():
            if field in allowed:
                setattr(task, field, value)
        await self.db.flush()
        await self.db.refresh(task)
        return task
