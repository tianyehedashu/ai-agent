"""
Product Info Prompt Template Repository - 产品信息提示词模板仓储
"""

from typing import Any
import uuid

from domains.agent.infrastructure.models.product_info_prompt_template import (
    ProductInfoPromptTemplate,
)
from libs.db.base_repository import OwnedRepositoryBase


class ProductInfoPromptTemplateRepository(OwnedRepositoryBase[ProductInfoPromptTemplate]):
    @property
    def model_class(self) -> type[ProductInfoPromptTemplate]:
        return ProductInfoPromptTemplate

    @property
    def anonymous_user_id_column(self) -> str:
        return "anonymous_user_id"

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        anonymous_user_id: str | None = None,
        capability_id: str = "",
        name: str = "",
        content: str | None = None,
        prompts: list | None = None,
    ) -> ProductInfoPromptTemplate:
        t = ProductInfoPromptTemplate(
            user_id=user_id,
            anonymous_user_id=anonymous_user_id,
            capability_id=capability_id,
            name=name,
            content=content,
            prompts=prompts,
        )
        self.db.add(t)
        await self.db.flush()
        await self.db.refresh(t)
        return t

    async def update(
        self,
        template_id: uuid.UUID,
        **kwargs: Any,
    ) -> ProductInfoPromptTemplate | None:
        t = await self.get_owned(template_id)
        if not t:
            return None
        allowed = {"name", "content", "prompts"}
        for field, value in kwargs.items():
            if field in allowed:
                setattr(t, field, value)
        await self.db.flush()
        await self.db.refresh(t)
        return t
