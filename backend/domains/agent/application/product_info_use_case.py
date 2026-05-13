"""
Product Info Use Case - 产品信息工作流用例

应用层编排：Job/Step CRUD、步骤执行与依赖注入，不依赖 LangGraph。
提示词优化为独立方法（可选），步骤执行直接渲染提示词后调 Runner。
"""

import asyncio
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from bootstrap.config_loader import get_app_config
from domains.agent.application.product_info_capability_runners import (
    RUNNERS,
    optimize_prompt_for_capability,
    render_meta_prompt,
)
from domains.agent.application.user_model_use_case import UserModelUseCase
from domains.agent.domain.product_info.constants import (
    CAPABILITIES,
    CAPABILITIES_REQUIRING_VISION,
    CAPABILITY_ORDER,
    DEFAULT_PROMPTS,
)
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.agent.infrastructure.models.product_info_job import (
    ProductInfoJob,
    ProductInfoJobStatus,
)
from domains.agent.infrastructure.models.product_info_job_step import (
    ProductInfoJobStepStatus,
)
from domains.agent.infrastructure.repositories.product_info_job_repository import (
    ProductInfoJobRepository,
)
from domains.agent.infrastructure.repositories.product_info_job_step_repository import (
    ProductInfoJobStepRepository,
)
from libs.db.database import get_session_context
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)
from libs.exceptions import NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


def _sort_order_for_capability(capability_id: str) -> int:
    for order, cid in CAPABILITY_ORDER:
        if cid == capability_id:
            return order
    return 0


class ProductInfoUseCase:
    """产品信息工作流用例"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.job_repo = ProductInfoJobRepository(db)
        self.step_repo = ProductInfoJobStepRepository(db)
        self._llm_gateway = LLMGateway(config=settings)
        self._user_model_uc = UserModelUseCase(db)

    # ─── Job CRUD ────────────────────────────────────────────────────

    async def create_job(
        self,
        principal_id: str,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        session_id: uuid.UUID | None = None,
        title: str | None = None,
        status: str = ProductInfoJobStatus.DRAFT,
    ) -> dict[str, Any]:
        """创建产品信息任务（Job）。"""
        job = await self.job_repo.create(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            session_id=session_id,
            title=title or "产品信息",
            status=status,
        )
        return _job_to_dict(job)

    async def list_jobs(
        self,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
        session_id: uuid.UUID | None = None,
    ) -> tuple[list[dict], int]:
        """列出当前用户的任务。"""
        filters: dict[str, Any] = {}
        if status:
            filters["status"] = status
        if session_id:
            filters["session_id"] = session_id
        items = await self.job_repo.find_owned(
            skip=skip,
            limit=limit,
            order_by="created_at",
            order_desc=True,
            **filters,
        )
        total = await self.job_repo.count_owned(**filters)
        return [_job_to_dict(j) for j in items], total

    async def get_job(self, job_id: uuid.UUID) -> dict[str, Any]:
        """获取任务详情（含 steps）。"""
        job = await self.job_repo.get_with_steps(job_id)
        if not job:
            raise NotFoundError("ProductInfoJob", str(job_id))
        return _job_to_dict_with_steps(job)

    async def delete_job(self, job_id: uuid.UUID) -> None:
        """删除任务。"""
        job = await self.job_repo.get_owned(job_id)
        if not job:
            raise NotFoundError("ProductInfoJob", str(job_id))
        await self.db.delete(job)
        await self.db.flush()

    # ─── 内部工具 ─────────────────────────────────────────────────────

    def _build_full_input(
        self,
        job: ProductInfoJob,
        capability_id: str,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """构建完整输入：注入所有已完成前序步骤的 output，再用 user_input 覆盖（用户编辑优先）。"""
        current_order = _sort_order_for_capability(capability_id)
        full_input: dict[str, Any] = {}
        for step in sorted(job.steps, key=lambda s: s.sort_order):
            if step.sort_order >= current_order:
                break
            if step.status != ProductInfoJobStepStatus.COMPLETED or not step.output_snapshot:
                continue
            full_input.update(step.output_snapshot)
        full_input.update(user_input)
        return full_input

    async def _resolve_model_override(
        self,
        capability_id: str,
        model_id: str | None,
    ) -> dict[str, Any]:
        """解析用户模型配置，校验能力所需特性。"""
        effective_model_id = model_id
        if not effective_model_id and capability_id in CAPABILITIES_REQUIRING_VISION:
            effective_model_id = settings.vision_model
            logger.info(
                "capability %s requires vision, using vision_model=%s",
                capability_id,
                effective_model_id,
            )

        resolved = await self._user_model_uc.resolve_model(effective_model_id)
        model_override: dict[str, Any] = {"model": resolved.model}
        if resolved.api_key:
            model_override["api_key"] = resolved.api_key
        if resolved.api_base:
            model_override["api_base"] = resolved.api_base

        cap_config = CAPABILITIES.get(capability_id)
        if cap_config and cap_config.required_features:
            model_info = get_app_config().models.get_model(resolved.model)
            if model_info:
                missing = cap_config.required_features - model_info.features
                if missing:
                    raise ValidationError(
                        f"模型 {resolved.model} 缺少能力「{cap_config.name}」所需的特性: {sorted(missing)}。"
                        f"请选择支持视觉的模型（如 qwen-vl-max）。"
                    )
        return model_override

    # ─── 提示词优化（可选，独立接口） ──────────────────────────────────

    async def optimize_prompt(
        self,
        job_id: uuid.UUID,
        capability_id: str,
        user_input: dict[str, Any],
        meta_prompt: str | None = None,
        model_id: str | None = None,
    ) -> str:
        """
        可选的提示词优化：调用 LLM 将用户提示词改写为更详细的版本。

        纯函数式调用，不修改 Step 记录；返回优化后的提示词文本供前端展示。
        """
        job = await self.job_repo.get_with_steps(job_id)
        if not job:
            raise NotFoundError("ProductInfoJob", str(job_id))

        if _sort_order_for_capability(capability_id) <= 0:
            raise ValidationError(f"Unknown capability_id: {capability_id}")

        full_input = self._build_full_input(job, capability_id, user_input)
        resolved_meta = meta_prompt or DEFAULT_PROMPTS.get(capability_id) or ""
        model_override = await self._resolve_model_override(capability_id, model_id)

        return await optimize_prompt_for_capability(
            capability_id,
            resolved_meta,
            full_input,
            self._llm_gateway,
            model_override=model_override,
        )

    # ─── 步骤执行 ─────────────────────────────────────────────────────

    async def run_step(
        self,
        job_id: uuid.UUID,
        capability_id: str,
        user_input: dict[str, Any],
        meta_prompt: str | None = None,
        prompt_template_id: uuid.UUID | None = None,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        """
        执行某一步：渲染提示词中的 {{param}} 占位符后直接调用 Runner。

        不再经过中间的 LLM 提示词生成步骤，提示词优化由独立接口 optimize_prompt 提供。
        """
        job = await self.job_repo.get_with_steps(job_id)
        if not job:
            raise NotFoundError("ProductInfoJob", str(job_id))

        sort_order = _sort_order_for_capability(capability_id)
        if sort_order <= 0:
            raise ValidationError(f"Unknown capability_id: {capability_id}")

        runner = RUNNERS.get(capability_id)
        if not runner:
            raise ValidationError(f"No runner for capability: {capability_id}")

        full_input = self._build_full_input(job, capability_id, user_input)
        resolved_meta = meta_prompt or DEFAULT_PROMPTS.get(capability_id) or ""
        prompt_to_use = render_meta_prompt(resolved_meta, full_input)

        existing = await self.step_repo.get_by_job_and_order(job_id, sort_order)
        if existing:
            step_id = existing.id
        else:
            step_rec = await self.step_repo.create(
                job_id=job_id,
                sort_order=sort_order,
                capability_id=capability_id,
                status=ProductInfoJobStepStatus.PENDING,
                input_snapshot=full_input,
                meta_prompt=resolved_meta,
                prompt_template_id=prompt_template_id,
            )
            step_id = step_rec.id

        await self.job_repo.update(job_id, status=ProductInfoJobStatus.RUNNING)
        model_override = await self._resolve_model_override(capability_id, model_id)

        await self.step_repo.update(
            step_id,
            input_snapshot=full_input,
            meta_prompt=resolved_meta,
            prompt_template_id=prompt_template_id,
            prompt_used=prompt_to_use,
            status=ProductInfoJobStepStatus.RUNNING,
            error_message=None,
        )
        await self.db.flush()

        try:
            output = await runner(
                full_input,
                prompt_to_use,
                self._llm_gateway,
                model_override=model_override,
            )
        except ValueError as e:
            await self.step_repo.update(
                step_id,
                status=ProductInfoJobStepStatus.FAILED,
                error_message=str(e),
            )
            await self._sync_job_status(job_id)
            raise ValidationError(str(e)) from e
        except Exception as e:
            logger.exception("run_step(%s) failed: %s", capability_id, e)
            await self.step_repo.update(
                step_id,
                status=ProductInfoJobStepStatus.FAILED,
                error_message=str(e),
            )
            await self._sync_job_status(job_id)
            raise

        await self.step_repo.update(
            step_id,
            output_snapshot=output,
            status=ProductInfoJobStepStatus.COMPLETED,
            error_message=None,
        )
        await self.db.flush()
        await self._sync_job_status(job_id)
        return await self.get_job(job_id)

    async def _sync_job_status(self, job_id: uuid.UUID) -> None:
        """根据所有 steps 的状态更新 Job 状态。"""
        job = await self.job_repo.get_with_steps(job_id)
        if not job:
            return
        statuses = [s.status for s in job.steps]
        if not statuses:
            return
        terminal = {
            ProductInfoJobStepStatus.COMPLETED,
            ProductInfoJobStepStatus.FAILED,
        }
        if all(s == ProductInfoJobStepStatus.COMPLETED for s in statuses):
            await self.job_repo.update(job_id, status=ProductInfoJobStatus.COMPLETED)
        elif all(s in terminal for s in statuses):
            # 含失败的全终态，或全为 FAILED
            await self.job_repo.update(job_id, status=ProductInfoJobStatus.PARTIAL)
        elif any(s in terminal for s in statuses):
            # 仍有 PENDING / RUNNING：未跑完
            await self.job_repo.update(job_id, status=ProductInfoJobStatus.PARTIAL)
        else:
            # 全部未进入终态（例如仅 PENDING）
            await self.job_repo.update(job_id, status=ProductInfoJobStatus.FAILED)
        await self.db.flush()

    def get_default_prompt(self, capability_id: str) -> str:
        """返回系统默认提示词（用于恢复模板）。"""
        return DEFAULT_PROMPTS.get(capability_id) or ""


def _build_execution_layers(
    caps_to_run: list[tuple[int, str]],
) -> list[list[tuple[int, str]]]:
    """按依赖关系将能力分组为并行执行层。

    同一层内的能力互不依赖、可并行执行；下一层依赖上层全部完成。
    """
    cap_ids = {c for _, c in caps_to_run}
    completed: set[str] = set()
    remaining = list(caps_to_run)
    layers: list[list[tuple[int, str]]] = []

    while remaining:
        layer = []
        still_remaining = []
        for order, cap_id in remaining:
            cfg = CAPABILITIES.get(cap_id)
            deps = set(cfg.dependencies) & cap_ids if cfg else set()
            if deps <= completed:
                layer.append((order, cap_id))
            else:
                still_remaining.append((order, cap_id))
        if not layer:
            layers.extend([[(o, c)] for o, c in still_remaining])
            break
        layers.append(layer)
        completed.update(c for _, c in layer)
        remaining = still_remaining

    return layers


async def _finalize_product_info_pipeline_job(job_id: uuid.UUID) -> None:
    """将仍为 RUNNING 的步骤标为失败，并据步骤状态聚合 Job（用于异常/关闭收尾）。"""
    async with get_session_context() as db:
        uc = ProductInfoUseCase(db)
        job = await uc.job_repo.get_with_steps(job_id)
        if job:
            for step in job.steps:
                if step.status == ProductInfoJobStepStatus.RUNNING:
                    await uc.step_repo.update(
                        step.id,
                        status=ProductInfoJobStepStatus.FAILED,
                        error_message="流水线中断或未正常结束",
                    )
        await uc._sync_job_status(job_id)


async def run_pipeline_async(
    job_id: uuid.UUID,
    user_id: uuid.UUID | None,
    anonymous_user_id: str | None,
    inputs: dict[str, Any],
    steps: list[str] | None = None,
) -> None:
    """
    后台一键执行：按依赖关系分层并行执行。

    同一层内无依赖的步骤并行执行（asyncio.gather），层间串行。
    每步使用独立的 DB session（get_session_context），确保中间结果
    立即提交对前端轮询可见。
    """
    ctx = PermissionContext(
        user_id=user_id,
        anonymous_user_id=anonymous_user_id,
        role="user",
    )
    set_permission_context(ctx)
    try:
        order_to_run = CAPABILITY_ORDER
        if steps:
            order_to_run = [(o, c) for o, c in order_to_run if c in steps]

        async with get_session_context() as db:
            step_repo = ProductInfoJobStepRepository(db)
            for order, cap_id in order_to_run:
                existing = await step_repo.get_by_job_and_order(job_id, order)
                if not existing:
                    await step_repo.create(
                        job_id=job_id,
                        sort_order=order,
                        capability_id=cap_id,
                        status=ProductInfoJobStepStatus.PENDING,
                    )

        layers = _build_execution_layers(order_to_run)
        cap_ids_set = {c for _, c in order_to_run}
        completed_caps: set[str] = set()

        async def _execute_one(cap_id: str) -> bool:
            """在独立 session 中执行单步，返回是否成功。"""
            async with get_session_context() as db:
                uc = ProductInfoUseCase(db)
                try:
                    await uc.run_step(
                        job_id=job_id,
                        capability_id=cap_id,
                        user_input=inputs,
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
                        sr = ProductInfoJobStepRepository(db)
                        rec = await sr.get_by_job_and_order(job_id, order)
                        if rec:
                            await sr.update(
                                rec.id,
                                status=ProductInfoJobStepStatus.FAILED,
                                error_message="依赖步骤未完成，已跳过",
                            )
            if not runnable:
                continue

            async with get_session_context() as db:
                sr = ProductInfoJobStepRepository(db)
                for order, _cid in runnable:
                    rec = await sr.get_by_job_and_order(job_id, order)
                    if rec:
                        await sr.update(
                            rec.id,
                            status=ProductInfoJobStepStatus.RUNNING,
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
        logger.warning("Product info pipeline cancelled (job_id=%s)", job_id)
        raise
    except Exception:
        logger.exception("Product info pipeline crashed (job_id=%s)", job_id)
        raise
    finally:
        try:
            await _finalize_product_info_pipeline_job(job_id)
        except Exception:
            logger.exception(
                "Failed to finalize product info pipeline job %s",
                job_id,
            )
        clear_permission_context()


def _job_to_dict(job: ProductInfoJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "user_id": str(job.user_id) if job.user_id else None,
        "anonymous_user_id": job.anonymous_user_id,
        "session_id": str(job.session_id) if job.session_id else None,
        "title": job.title,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


def _job_to_dict_with_steps(job: ProductInfoJob) -> dict[str, Any]:
    d = _job_to_dict(job)
    d["steps"] = [
        {
            "id": str(s.id),
            "job_id": str(s.job_id),
            "sort_order": s.sort_order,
            "capability_id": s.capability_id,
            "input_snapshot": s.input_snapshot,
            "output_snapshot": s.output_snapshot,
            "meta_prompt": s.meta_prompt,
            "generated_prompt": s.generated_prompt,
            "prompt_used": s.prompt_used,
            "prompt_template_id": str(s.prompt_template_id) if s.prompt_template_id else None,
            "status": s.status,
            "error_message": s.error_message,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sorted(job.steps, key=lambda x: x.sort_order)
    ]
    return d
