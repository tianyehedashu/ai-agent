"""
Product Info Prompt Service - 产品信息提示词模板服务

提供系统默认提示词与用户模板 CRUD。
"""

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from domains.agent.domain.product_info.constants import (
    CAPABILITIES,
    DEFAULT_IMAGE_GEN_PROMPTS_8,
    DEFAULT_PROMPTS,
    META_PROMPT_PARAMS,
)
from domains.agent.infrastructure.repositories.product_info_prompt_template_repository import (
    ProductInfoPromptTemplateRepository,
)
from libs.exceptions import NotFoundError
from utils.logging import get_logger

logger = get_logger(__name__)


def list_capabilities() -> list[dict[str, Any]]:
    """返回所有原子能力列表（含完整元数据，供前端动态渲染）。"""
    result: list[dict[str, Any]] = []
    for cfg in sorted(CAPABILITIES.values(), key=lambda c: c.sort_order):
        model_type = "image" if "vision" in cfg.required_features else "text"
        result.append(
            {
                "id": cfg.id,
                "name": cfg.name,
                "sort_order": cfg.sort_order,
                "model_type": model_type,
                "output_key": cfg.output_key,
                "dependencies": list(cfg.dependencies),
                "input_fields": list(cfg.input_fields),
                "meta_prompt_params": [{"key": k, "label": lb} for k, lb in cfg.meta_prompt_params],
                "required_features": list(cfg.required_features),
            }
        )
    return result


def get_default_prompt(capability_id: str) -> str:
    """返回系统默认提示词（用于恢复模板）。"""
    return DEFAULT_PROMPTS.get(capability_id) or ""


def get_default_image_gen_prompts() -> list[str]:
    """返回 8 图默认提示词数组（image_gen_prompts 用）。"""
    return list(DEFAULT_IMAGE_GEN_PROMPTS_8)


def list_meta_prompt_params(capability_id: str) -> list[dict[str, str]]:
    """返回某能力下元提示词可用的占位符参数，用于 UI 插入 {{param}}。"""
    params = META_PROMPT_PARAMS.get(capability_id, [])
    return [{"key": k, "label": label} for k, label in params]


class ProductInfoPromptTemplateUseCase:
    """产品信息提示词模板用例"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProductInfoPromptTemplateRepository(db)

    async def list_templates(
        self,
        capability_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict], int]:
        """列出某能力下的用户模板。"""
        # 按 capability_id 过滤需在 find_owned 里支持；OwnedRepositoryBase 支持 **filters
        items = await self.repo.find_owned(
            skip=skip,
            limit=limit,
            order_by="updated_at",
            order_desc=True,
            capability_id=capability_id,
        )
        total = await self.repo.count_owned(capability_id=capability_id)
        return [_template_to_dict(t) for t in items], total

    async def create_template(
        self,
        capability_id: str,
        name: str,
        content: str | None = None,
        prompts: list[str] | None = None,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
    ) -> dict[str, Any]:
        """保存为用户模板。"""
        t = await self.repo.create(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            capability_id=capability_id,
            name=name,
            content=content,
            prompts=prompts,
        )
        await self.db.flush()
        await self.db.refresh(t)
        return _template_to_dict(t)

    async def get_template(self, template_id: uuid.UUID) -> dict[str, Any]:
        """获取单条模板。"""
        t = await self.repo.get_owned(template_id)
        if not t:
            raise NotFoundError("ProductInfoPromptTemplate", str(template_id))
        return _template_to_dict(t)

    async def update_template(
        self,
        template_id: uuid.UUID,
        name: str | None = None,
        content: str | None = None,
        prompts: list[str] | None = None,
    ) -> dict[str, Any]:
        """更新用户模板。"""
        t = await self.repo.update(template_id, name=name, content=content, prompts=prompts)
        if not t:
            raise NotFoundError("ProductInfoPromptTemplate", str(template_id))
        return _template_to_dict(t)

    async def delete_template(self, template_id: uuid.UUID) -> None:
        """删除用户模板。"""
        t = await self.repo.get_owned(template_id)
        if not t:
            raise NotFoundError("ProductInfoPromptTemplate", str(template_id))
        await self.db.delete(t)
        await self.db.flush()


def _template_to_dict(t: Any) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "user_id": str(t.user_id) if t.user_id else None,
        "anonymous_user_id": t.anonymous_user_id,
        "capability_id": t.capability_id,
        "name": t.name,
        "content": t.content,
        "prompts": t.prompts,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
