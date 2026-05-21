"""Listing Studio Prompt Template Repository"""

from typing import Any
import uuid

from domains.agent.infrastructure.models.listing_studio_prompt_template import (
    ListingStudioPromptTemplate,
)
from libs.db.base_repository import TenantScopedRepositoryBase
from libs.db.tenant_resolve import resolve_tenant_id_for_write


class ListingStudioPromptTemplateRepository(TenantScopedRepositoryBase[ListingStudioPromptTemplate]):
    @property
    def model_class(self) -> type[ListingStudioPromptTemplate]:
        return ListingStudioPromptTemplate

    async def create(
        self,
        *,
        capability_id: str = "",
        name: str = "",
        content: str | None = None,
        prompts: list | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> ListingStudioPromptTemplate:
        resolved = tenant_id or await resolve_tenant_id_for_write(self.db)
        t = ListingStudioPromptTemplate(
            tenant_id=resolved,
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
        t = await self.get_in_tenants(template_id)
        if not t:
            return None
        allowed = {"name", "content", "prompts"}
        for field, value in kwargs.items():
            if field in allowed:
                setattr(t, field, value)
        await self.db.flush()
        await self.db.refresh(t)
        return t
