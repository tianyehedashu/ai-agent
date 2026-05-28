"""
Listing Studio API deprecation helpers for legacy /product-info routes.
"""

from fastapi import Response

from libs.api.paths import api_v1_path

LISTING_STUDIO_API_PREFIX = api_v1_path("listing-studio")
LEGACY_PRODUCT_INFO_API_PREFIX = api_v1_path("product-info")


def apply_listing_studio_deprecation_headers(response: Response) -> None:
    """Mark response as deprecated; point clients to listing-studio."""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'<{LISTING_STUDIO_API_PREFIX}>; rel="successor-version"'


async def listing_studio_deprecation_headers(response: Response) -> None:
    """FastAPI dependency: add Deprecation + Link on legacy product-info routes."""
    apply_listing_studio_deprecation_headers(response)
