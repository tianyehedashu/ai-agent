"""
Product Info Job Repository - 产品信息任务仓储
"""

from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from domains.agent.infrastructure.models.product_info_job import ProductInfoJob
from libs.db.base_repository import OwnedRepositoryBase


class ProductInfoJobRepository(OwnedRepositoryBase[ProductInfoJob]):
    @property
    def model_class(self) -> type[ProductInfoJob]:
        return ProductInfoJob

    @property
    def anonymous_user_id_column(self) -> str:
        return "anonymous_user_id"

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        session_id: uuid.UUID | None = None,
        title: str | None = None,
        status: str = "draft",
    ) -> ProductInfoJob:
        job = ProductInfoJob(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            session_id=session_id,
            title=title,
            status=status,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def update(self, job_id: uuid.UUID, **kwargs: Any) -> ProductInfoJob | None:
        job = await self.get_owned(job_id)
        if not job:
            return None
        allowed = {"title", "status"}
        for field, value in kwargs.items():
            if field in allowed:
                setattr(job, field, value)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def get_with_steps(self, job_id: uuid.UUID) -> ProductInfoJob | None:
        q = (
            select(ProductInfoJob)
            .where(ProductInfoJob.id == job_id)
            .options(selectinload(ProductInfoJob.steps))
        )
        q = self._apply_ownership_filter(q)
        result = await self.db.execute(q)
        return result.unique().scalar_one_or_none()
