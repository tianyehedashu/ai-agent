"""Agent 侧实现 Gateway ``ListingStudioLocalImagePort``（bootstrap 注册）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.agent.application.listing_studio_image_factory import (
    create_listing_studio_image_service,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.agent.application.listing_studio_image_service import ListingStudioImageService


class AgentListingStudioLocalImagePort:
    """将 ``ListingStudioImageService`` 适配为 Gateway 视觉内联端口。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._service: ListingStudioImageService | None = None

    async def _service_or_create(self) -> ListingStudioImageService:
        if self._service is None:
            self._service = create_listing_studio_image_service(self._session)
        return self._service

    async def resolve_local_image_path(self, filename: str) -> Path | None:
        service = await self._service_or_create()
        return await service.resolve_local_image_path(filename)


def listing_studio_local_image_port_for_session(
    session: AsyncSession,
) -> AgentListingStudioLocalImagePort:
    return AgentListingStudioLocalImagePort(session)


__all__ = [
    "AgentListingStudioLocalImagePort",
    "listing_studio_local_image_port_for_session",
]
