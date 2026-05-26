"""Listing Studio 本地图片端口注册表（bootstrap 注入，避免 Gateway 反向 import Agent）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from domains.gateway.application.ports import (
    ListingStudioLocalImagePort,
    ListingStudioLocalImagePortFactory,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_factory: ListingStudioLocalImagePortFactory | None = None


def register_listing_studio_local_image_port_factory(
    factory: ListingStudioLocalImagePortFactory,
) -> None:
    global _factory
    _factory = factory


def get_listing_studio_local_image_port(session: AsyncSession) -> ListingStudioLocalImagePort:
    if _factory is None:
        msg = (
            "ListingStudioLocalImagePort 未注册；"
            "请在 bootstrap lifespan 调用 register_listing_studio_local_image_port_factory"
        )
        raise RuntimeError(msg)
    return _factory(session)


__all__ = [
    "get_listing_studio_local_image_port",
    "register_listing_studio_local_image_port_factory",
]
