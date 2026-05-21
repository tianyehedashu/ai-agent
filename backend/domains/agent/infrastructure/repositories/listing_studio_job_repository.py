"""
Listing Studio Job Repository - Listing Studio 任务仓储
"""

from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from domains.agent.infrastructure.models.listing_studio_job import ListingStudioJob
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.db.tenant_resolve import resolve_tenant_id_for_write


class ListingStudioJobRepository(TenantScopedRepositoryBase[ListingStudioJob]):
    @property
    def model_class(self) -> type[ListingStudioJob]:
        return ListingStudioJob

    async def create(
        self,
        *,
        session_id: uuid.UUID | None = None,
        title: str | None = None,
        status: str = "draft",
        tenant_id: uuid.UUID | None = None,
    ) -> ListingStudioJob:
        resolved = tenant_id or await resolve_tenant_id_for_write(self.db)
        job = ListingStudioJob(
            tenant_id=resolved,
            session_id=session_id,
            title=title,
            status=status,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def update(self, job_id: uuid.UUID, **kwargs: Any) -> ListingStudioJob | None:
        job = await self.get_in_tenants(job_id)
        if not job:
            return None
        allowed = {"title", "status"}
        for field, value in kwargs.items():
            if field in allowed:
                setattr(job, field, value)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def get_with_steps(self, job_id: uuid.UUID) -> ListingStudioJob | None:
        q = (
            select(ListingStudioJob)
            .where(ListingStudioJob.id == job_id)
            .options(selectinload(ListingStudioJob.steps))
        )
        q = self._apply_tenant_scope(q)
        result = await self.db.execute(q)
        return result.unique().scalar_one_or_none()
