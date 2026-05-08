"""
Product Image Gen Task Use Case - 8 图生成任务应用层

封装创建、列表、详情，供 Presentation 层调用。
创建任务后异步调用 ImageGenerator 生成图片。
"""

import asyncio
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.infrastructure.llm.image_generator import (
    ImageGenerationResult,
    ImageGenerator,
)
from domains.agent.infrastructure.models.product_image_gen_task import (
    ProductImageGenTask,
    ProductImageGenTaskStatus,
)
from domains.agent.infrastructure.repositories.product_image_gen_task_repository import (
    ProductImageGenTaskRepository,
)
from exceptions import NotFoundError
from libs.db.database import get_session_factory
from libs.db.permission_context import PermissionContext, set_permission_context
from libs.storage.local_image_store import save_or_passthrough
from utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["ProductImageGenTaskUseCase"]


def _task_to_dict(task: ProductImageGenTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "job_id": str(task.job_id) if task.job_id else None,
        "status": task.status,
        "prompts": task.prompts,
        "result_images": task.result_images,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


async def _generate_images_background(
    task_id: uuid.UUID,
    prompts: list[dict[str, Any]],
    image_generator: ImageGenerator,
    user_id: uuid.UUID | None,
    anonymous_user_id: str | None,
    api_key_override: str | None = None,
    api_base_override: str | None = None,
) -> None:
    """后台异步生成 8 张图片，逐条调用 ImageGenerator 并更新数据库。"""
    set_permission_context(
        PermissionContext(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
        )
    )
    session_factory = get_session_factory()
    async with session_factory() as db:
        repo = ProductImageGenTaskRepository(db)

        try:
            await repo.update(task_id, status=ProductImageGenTaskStatus.RUNNING)
            await db.commit()

            result_images: list[dict[str, Any]] = []
            errors: list[str] = []

            for item in prompts:
                slot = item.get("slot", 0)
                prompt_text = item.get("prompt", "")
                if not prompt_text.strip():
                    result_images.append({"slot": slot, "url": "", "skipped": True})
                    continue

                provider = item.get("provider", "volcengine")
                model = item.get("model")
                size = item.get("size")
                ref_url = item.get("reference_image_url")
                strength = item.get("strength")

                try:
                    result: ImageGenerationResult = await image_generator.generate(
                        prompt=prompt_text,
                        provider=provider,
                        model=model,
                        size=size,
                        n=1,
                        reference_image_url=ref_url,
                        strength=strength,
                        api_key_override=api_key_override,
                        api_base_override=api_base_override,
                    )
                    if result.success and result.images:
                        url = save_or_passthrough(result.images[0])
                        result_images.append({"slot": slot, "url": url})
                    else:
                        err_msg = result.error or "Unknown error"
                        errors.append(f"Slot {slot}: {err_msg}")
                        result_images.append({"slot": slot, "url": "", "error": err_msg})
                except Exception as e:
                    logger.exception("Image generation failed for slot %d", slot)
                    errors.append(f"Slot {slot}: {e}")
                    result_images.append({"slot": slot, "url": "", "error": str(e)})

            has_any_image = any(img.get("url") for img in result_images)
            final_status = (
                ProductImageGenTaskStatus.COMPLETED
                if has_any_image
                else ProductImageGenTaskStatus.FAILED
            )
            error_message = "; ".join(errors) if errors else None

            await repo.update(
                task_id,
                status=final_status,
                result_images=result_images,
                error_message=error_message[:500] if error_message else None,
            )
            await db.commit()
            logger.info(
                "Image gen task %s finished: status=%s, images=%d",
                task_id,
                final_status,
                sum(1 for i in result_images if i.get("url")),
            )

        except Exception as e:
            logger.exception("Background image generation failed for task %s", task_id)
            try:
                await repo.update(
                    task_id,
                    status=ProductImageGenTaskStatus.FAILED,
                    error_message=str(e)[:500],
                )
                await db.commit()
            except Exception:
                logger.exception("Failed to update task %s to FAILED", task_id)


_background_tasks: set[asyncio.Task[None]] = set()


class ProductImageGenTaskUseCase:
    """8 图生成任务用例"""

    def __init__(
        self,
        db: AsyncSession,
        image_generator: ImageGenerator | None = None,
    ) -> None:
        self.db = db
        self.repo = ProductImageGenTaskRepository(db)
        self.image_generator = image_generator

    async def create(
        self,
        user_id: uuid.UUID | None,
        anonymous_user_id: str | None,
        job_id: uuid.UUID | None = None,
        prompts: list | None = None,
        api_key_override: str | None = None,
        api_base_override: str | None = None,
    ) -> dict[str, Any]:
        """创建 8 图任务并异步启动图片生成。

        api_key_override / api_base_override 由 Router 通过
        UserModelUseCase.resolve_image_gen_model 解析后传入。
        """
        task = await self.repo.create(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            job_id=job_id,
            prompts=prompts or [],
            status=ProductImageGenTaskStatus.PENDING,
        )
        await self.db.flush()
        await self.db.refresh(task)
        task_dict = _task_to_dict(task)

        if self.image_generator and prompts:
            bg = asyncio.create_task(
                _generate_images_background(
                    task_id=task.id,
                    prompts=prompts,
                    image_generator=self.image_generator,
                    user_id=user_id,
                    anonymous_user_id=anonymous_user_id,
                    api_key_override=api_key_override,
                    api_base_override=api_base_override,
                )
            )
            _background_tasks.add(bg)
            bg.add_done_callback(_background_tasks.discard)
            task_dict["status"] = ProductImageGenTaskStatus.PENDING

        return task_dict

    async def list_tasks(
        self,
        skip: int = 0,
        limit: int = 20,
        job_id: uuid.UUID | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """列表（当前用户），可按 job_id 过滤。"""
        filters: dict[str, Any] = {}
        if job_id:
            filters["job_id"] = job_id
        items = await self.repo.find_owned(
            skip=skip,
            limit=limit,
            order_by="created_at",
            order_desc=True,
            **filters,
        )
        total = await self.repo.count_owned(**filters)
        return ([_task_to_dict(t) for t in items], total)

    async def get_task(self, task_id: uuid.UUID) -> dict[str, Any]:
        """详情（当前用户）。"""
        task = await self.repo.get_owned(task_id)
        if not task:
            raise NotFoundError("ProductImageGenTask", str(task_id))
        return _task_to_dict(task)
