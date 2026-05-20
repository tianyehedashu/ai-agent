"""
Legacy Product Info API router (deprecated).

Mounts the same handlers as listing_studio_router under /api/v1/product-info
with Deprecation and Link response headers.
"""

from fastapi import APIRouter, Depends

from domains.agent.presentation.listing_studio_deprecation import (
    listing_studio_deprecation_headers,
)
from domains.agent.presentation.listing_studio_router import router as listing_studio_router

router = APIRouter(
    dependencies=[Depends(listing_studio_deprecation_headers)],
)
router.include_router(listing_studio_router)
