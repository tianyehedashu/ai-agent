"""
Listing Studio Use Case - Listing 工作流用例

应用层编排：Job/Step CRUD、步骤执行与依赖注入，不依赖 LangGraph。
提示词优化为独立方法（可选），步骤执行直接渲染提示词后调 Runner。
"""

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import settings
from domains.agent.application.chat_model_resolution_use_case import ChatModelResolutionUseCase
from domains.agent.application.listing_studio_capability_runners import (
    RUNNERS,
    optimize_prompt_for_capability,
    render_meta_prompt,
)
from domains.agent.application.listing_studio_job_mapper import job_to_dict, job_to_dict_with_steps
from domains.agent.application.ports.model_catalog_port import ModelCatalogPort
from domains.agent.domain.listing_studio.capability_policy import (
    missing_capability_features,
)
from domains.agent.domain.listing_studio.constants import (
    CAPABILITIES,
    CAPABILITY_ORDER,
    DEFAULT_PROMPTS,
)
from domains.agent.domain.listing_studio.job_status_policy import aggregate_job_status
from domains.agent.domain.listing_studio.types import (
    ListingStudioJobStatus,
    ListingStudioJobStepStatus,
)
from domains.agent.infrastructure.llm.agent_llm_facade import AgentLlmFacade
from domains.agent.infrastructure.models.listing_studio_job import ListingStudioJob
from domains.agent.infrastructure.repositories.listing_studio_job_repository import (
    ListingStudioJobRepository,
)
from domains.agent.infrastructure.repositories.listing_studio_job_step_repository import (
    ListingStudioJobStepRepository,
)
from libs.exceptions import NotFoundError, ValidationError
from utils.logging import get_logger

logger = get_logger(__name__)


def _sort_order_for_capability(capability_id: str) -> int:
    for order, cid in CAPABILITY_ORDER:
        if cid == capability_id:
            return order
    return 0


class ListingStudioUseCase:
    """Listing Studio 工作流用例"""

    def __init__(self, db: AsyncSession, catalog: ModelCatalogPort) -> None:
        self.db = db
        self._catalog = catalog
        self.job_repo = ListingStudioJobRepository(db)
        self.step_repo = ListingStudioJobStepRepository(db)
        self._llm_gateway = AgentLlmFacade(config=settings, model_catalog=catalog)
        self._model_resolution = ChatModelResolutionUseCase(db, catalog)

    # ─── Job CRUD ────────────────────────────────────────────────────

    async def create_job(
        self,
        principal_id: str,
        session_id: uuid.UUID | None = None,
        title: str | None = None,
        status: str = ListingStudioJobStatus.DRAFT,
    ) -> dict[str, Any]:
        """创建 Listing 创作任务（Job）。``principal_id`` 保留供审计扩展。"""
        _ = principal_id
        job = await self.job_repo.create(
            session_id=session_id,
            title=title or "Listing 创作",
            status=status,
        )
        return job_to_dict(job)

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
        items = await self.job_repo.find_for_tenants(
            skip=skip,
            limit=limit,
            order_by="created_at",
            order_desc=True,
            **filters,
        )
        total = await self.job_repo.count_for_tenants(**filters)
        return [job_to_dict(j) for j in items], total

    async def get_job(self, job_id: uuid.UUID) -> dict[str, Any]:
        """获取任务详情（含 steps）。"""
        job = await self.job_repo.get_with_steps(job_id)
        if not job:
            raise NotFoundError("ListingStudioJob", str(job_id))
        return job_to_dict_with_steps(job)

    async def delete_job(self, job_id: uuid.UUID) -> None:
        """删除任务。"""
        job = await self.job_repo.get_in_tenants(job_id)
        if not job:
            raise NotFoundError("ListingStudioJob", str(job_id))
        await self.db.delete(job)
        await self.db.flush()

    # ─── 内部工具 ─────────────────────────────────────────────────────

    def _build_full_input(
        self,
        job: ListingStudioJob,
        capability_id: str,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """构建完整输入：注入所有已完成前序步骤的 output，再用 user_input 覆盖（用户编辑优先）。"""
        current_order = _sort_order_for_capability(capability_id)
        full_input: dict[str, Any] = {}
        for step in sorted(job.steps, key=lambda s: s.sort_order):
            if step.sort_order >= current_order:
                break
            if step.status != ListingStudioJobStepStatus.COMPLETED or not step.output_snapshot:
                continue
            full_input.update(step.output_snapshot)
        full_input.update(user_input)
        return full_input

    async def _resolve_model_override(
        self,
        capability_id: str,
        model_id: str | None,
    ) -> dict[str, Any]:
        """解析用户模型配置，校验能力所需特性（真源：Gateway 可见目录）。"""
        cap_config = CAPABILITIES.get(capability_id)
        requires_vision = cap_config is not None and "vision" in cap_config.required_features

        if requires_vision:
            allowed = await self._model_resolution.visible_image_system_model_ids()
            resolved = await self._model_resolution.resolve_vision_chat_model(
                model_id,
                allowed_image_system_ids=allowed,
            )
        else:
            allowed = await self._model_resolution.visible_text_system_model_ids()
            resolved = await self._model_resolution.resolve_text_chat_model(
                model_id,
                allowed_text_system_ids=allowed,
            )
        model_override: dict[str, Any] = {"model": resolved.model}

        if cap_config and cap_config.required_features:
            catalog_features = await self._catalog.model_features(resolved.model)
            if catalog_features is None:
                raise ValidationError(
                    f"模型 {resolved.model} 未在 Gateway 目录注册或缺少能力元数据；"
                    f"请选择已在 Gateway 注册且支持所需能力的模型。"
                )
            missing = missing_capability_features(cap_config.required_features, catalog_features)
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
            raise NotFoundError("ListingStudioJob", str(job_id))

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
            raise NotFoundError("ListingStudioJob", str(job_id))

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
                status=ListingStudioJobStepStatus.PENDING,
                input_snapshot=full_input,
                meta_prompt=resolved_meta,
                prompt_template_id=prompt_template_id,
            )
            step_id = step_rec.id

        await self.job_repo.update(job_id, status=ListingStudioJobStatus.RUNNING)
        model_override = await self._resolve_model_override(capability_id, model_id)

        await self.step_repo.update(
            step_id,
            input_snapshot=full_input,
            meta_prompt=resolved_meta,
            prompt_template_id=prompt_template_id,
            prompt_used=prompt_to_use,
            status=ListingStudioJobStepStatus.RUNNING,
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
                status=ListingStudioJobStepStatus.FAILED,
                error_message=str(e),
            )
            await self.sync_job_status(job_id)
            raise ValidationError(str(e)) from e
        except Exception as e:
            logger.exception("run_step(%s) failed: %s", capability_id, e)
            await self.step_repo.update(
                step_id,
                status=ListingStudioJobStepStatus.FAILED,
                error_message=str(e),
            )
            await self.sync_job_status(job_id)
            raise

        await self.step_repo.update(
            step_id,
            output_snapshot=output,
            status=ListingStudioJobStepStatus.COMPLETED,
            error_message=None,
        )
        await self.db.flush()
        await self.sync_job_status(job_id)
        return await self.get_job(job_id)

    async def sync_job_status(self, job_id: uuid.UUID) -> None:
        """根据所有 steps 的状态更新 Job 状态。"""
        job = await self.job_repo.get_with_steps(job_id)
        if not job:
            return
        new_status = aggregate_job_status([s.status for s in job.steps])
        if new_status is None:
            return
        await self.job_repo.update(job_id, status=new_status)
        await self.db.flush()

    def get_default_prompt(self, capability_id: str) -> str:
        """返回系统默认提示词（用于恢复模板）。"""
        return DEFAULT_PROMPTS.get(capability_id) or ""
