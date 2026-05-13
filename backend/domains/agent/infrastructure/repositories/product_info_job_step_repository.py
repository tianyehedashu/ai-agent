"""
Product Info Job Step Repository - 产品信息步骤仓储

不继承 OwnedRepositoryBase：Step 始终通过 Job 的权限间接保护，
UseCase 层在操作 Step 前必须先校验 Job 归属权限。
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.models.product_info_job_step import ProductInfoJobStep


class ProductInfoJobStepRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        job_id: uuid.UUID,
        sort_order: int,
        capability_id: str,
        status: str = "pending",
        input_snapshot: dict | None = None,
        output_snapshot: dict | None = None,
        meta_prompt: str | None = None,
        generated_prompt: str | None = None,
        prompt_used: str | None = None,
        prompt_template_id: uuid.UUID | None = None,
        error_message: str | None = None,
    ) -> ProductInfoJobStep:
        step = ProductInfoJobStep(
            job_id=job_id,
            sort_order=sort_order,
            capability_id=capability_id,
            status=status,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            meta_prompt=meta_prompt,
            generated_prompt=generated_prompt,
            prompt_used=prompt_used,
            prompt_template_id=prompt_template_id,
            error_message=error_message,
        )
        self.db.add(step)
        await self.db.flush()
        await self.db.refresh(step)
        return step

    async def get_by_job_and_order(
        self,
        job_id: uuid.UUID,
        sort_order: int,
    ) -> ProductInfoJobStep | None:
        q = select(ProductInfoJobStep).where(
            ProductInfoJobStep.job_id == job_id,
            ProductInfoJobStep.sort_order == sort_order,
        )
        result = await self.db.execute(q)
        return result.scalar_one_or_none()

    async def list_by_job_id(self, job_id: uuid.UUID) -> list[ProductInfoJobStep]:
        q = (
            select(ProductInfoJobStep)
            .where(ProductInfoJobStep.job_id == job_id)
            .order_by(ProductInfoJobStep.sort_order)
        )
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def update(
        self,
        step_id: uuid.UUID,
        **kwargs,
    ) -> ProductInfoJobStep | None:
        q = select(ProductInfoJobStep).where(ProductInfoJobStep.id == step_id)
        result = await self.db.execute(q)
        step = result.scalar_one_or_none()
        if not step:
            return None
        allowed = {
            "input_snapshot",
            "output_snapshot",
            "meta_prompt",
            "generated_prompt",
            "prompt_used",
            "prompt_template_id",
            "status",
            "error_message",
        }
        for field, value in kwargs.items():
            if field in allowed:
                setattr(step, field, value)
        await self.db.flush()
        await self.db.refresh(step)
        return step
