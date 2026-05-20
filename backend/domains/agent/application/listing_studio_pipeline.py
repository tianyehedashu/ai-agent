"""Listing Studio 后台流水线编排。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

from domains.agent.application.listing_studio_use_case import ListingStudioUseCase
from domains.agent.domain.listing_studio.constants import CAPABILITIES, CAPABILITY_ORDER
from domains.agent.domain.listing_studio.pipeline_policy import build_execution_layers
from domains.agent.domain.listing_studio.types import ListingStudioJobStepStatus
from domains.agent.infrastructure.repositories.listing_studio_job_step_repository import (
    ListingStudioJobStepRepository,
)
from domains.gateway.application.sql_model_catalog import get_model_catalog_adapter
from libs.db.database import get_session_context
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)
from utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["run_pipeline_async"]


async def _finalize_listing_studio_pipeline_job(job_id: UUID) -> None:
    async with get_session_context() as db:
        uc = ListingStudioUseCase(db, catalog=get_model_catalog_adapter(db))
        job = await uc.job_repo.get_with_steps(job_id)
        if job:
            for step in job.steps:
                if step.status == ListingStudioJobStepStatus.RUNNING:
                    await uc.step_repo.update(
                        step.id,
                        status=ListingStudioJobStepStatus.FAILED,
                        error_message="流水线中断或未正常结束",
                    )
        await uc.sync_job_status(job_id)


async def run_pipeline_async(
    job_id: UUID,
    user_id: UUID | None,
    anonymous_user_id: str | None,
    inputs: dict[str, Any],
    steps: list[str] | None = None,
    model_overrides: dict[str, str] | None = None,
) -> None:
    """后台一键执行：按依赖关系分层并行执行。"""
    ctx = PermissionContext(
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        role="user",
    )
    set_permission_context(ctx)
    overrides = model_overrides or {}
    try:
        order_to_run = CAPABILITY_ORDER
        if steps:
            order_to_run = [(o, c) for o, c in order_to_run if c in steps]

        async with get_session_context() as db:
            step_repo = ListingStudioJobStepRepository(db)
            for order, cap_id in order_to_run:
                existing = await step_repo.get_by_job_and_order(job_id, order)
                if not existing:
                    await step_repo.create(
                        job_id=job_id,
                        sort_order=order,
                        capability_id=cap_id,
                        status=ListingStudioJobStepStatus.PENDING,
                    )

        layers = build_execution_layers(order_to_run)
        cap_ids_set = {c for _, c in order_to_run}
        completed_caps: set[str] = set()

        async def _execute_one(cap_id: str) -> bool:
            async with get_session_context() as db:
                uc = ListingStudioUseCase(db, catalog=get_model_catalog_adapter(db))
                try:
                    await uc.run_step(
                        job_id=job_id,
                        capability_id=cap_id,
                        user_input=inputs,
                        model_id=overrides.get(cap_id),
                    )
                    return True
                except Exception:
                    logger.exception(
                        "Pipeline step %s failed for job %s",
                        cap_id,
                        job_id,
                    )
                    return False

        for layer in layers:
            runnable: list[tuple[int, str]] = []
            for order, cap_id in layer:
                cfg = CAPABILITIES.get(cap_id)
                deps = set(cfg.dependencies) & cap_ids_set if cfg else set()
                if deps <= completed_caps:
                    runnable.append((order, cap_id))
                else:
                    async with get_session_context() as db:
                        sr = ListingStudioJobStepRepository(db)
                        rec = await sr.get_by_job_and_order(job_id, order)
                        if rec:
                            await sr.update(
                                rec.id,
                                status=ListingStudioJobStepStatus.FAILED,
                                error_message="依赖步骤未完成，已跳过",
                            )
            if not runnable:
                continue

            async with get_session_context() as db:
                sr = ListingStudioJobStepRepository(db)
                for order, _cid in runnable:
                    rec = await sr.get_by_job_and_order(job_id, order)
                    if rec:
                        await sr.update(
                            rec.id,
                            status=ListingStudioJobStepStatus.RUNNING,
                        )

            if len(runnable) == 1:
                ok = await _execute_one(runnable[0][1])
                results = [ok]
            else:
                results = list(
                    await asyncio.gather(
                        *[_execute_one(cap_id) for _, cap_id in runnable],
                    )
                )

            for (_, cap_id), ok in zip(runnable, results, strict=True):
                if ok:
                    completed_caps.add(cap_id)

    except asyncio.CancelledError:
        logger.warning("Listing studio pipeline cancelled (job_id=%s)", job_id)
        raise
    except Exception:
        logger.exception("Listing studio pipeline crashed (job_id=%s)", job_id)
        raise
    finally:
        try:
            await _finalize_listing_studio_pipeline_job(job_id)
        except Exception:
            logger.exception("Failed to finalize listing studio pipeline job %s", job_id)
        clear_permission_context()
