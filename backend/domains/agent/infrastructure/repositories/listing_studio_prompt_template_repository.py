"""
Listing Studio Prompt Template Repository - Listing Studio 提示词模板仓储
"""

from typing import Any
import uuid

from domains.agent.infrastructure.models.listing_studio_prompt_template import (
    ListingStudioPromptTemplate,
)
from libs.db.base_repository import OwnedRepositoryBase


class ListingStudioPromptTemplateRepository(OwnedRepositoryBase[ListingStudioPromptTemplate]):
    @property
    def model_class(self) -> type[ListingStudioPromptTemplate]:
        return ListingStudioPromptTemplate

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
    ) -> ListingStudioPromptTemplate:
        t = ListingStudioPromptTemplate(
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
    ) -> ListingStudioPromptTemplate | None:
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
