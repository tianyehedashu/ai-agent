"""Gateway 模型分页列表 response 组装。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from domains.gateway.application.catalog.model_list_pipeline import ModelListPageResult
from domains.gateway.presentation.schemas.common import (
    GatewayModelListResponse,
    ModelConnectivitySummary,
    PaginatedSelectorModels,
    PersonalModelListResponse,
    PersonalModelResponse,
)
from domains.gateway.presentation.schemas.gateway_model_response import build_gateway_model_response
from libs.api.pagination import build_page

if TYPE_CHECKING:
    from domains.gateway.infrastructure.models.system_gateway import SystemProviderCredential


def build_gateway_model_list_response(
    page: ModelListPageResult,
    *,
    include_system_credential: bool = False,
    credentials_by_id: dict[Any, SystemProviderCredential] | None = None,
    team_credentials_by_id: dict[Any, object] | None = None,
) -> GatewayModelListResponse:
    items = [
        build_gateway_model_response(
            row,
            include_system_credential=include_system_credential,
            credentials_by_id=credentials_by_id,
            team_credentials_by_id=team_credentials_by_id,
        )
        for row in page.items
    ]
    envelope = build_page(
        items=items,
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
    return GatewayModelListResponse(
        **envelope.model_dump(),
        connectivity_summary=ModelConnectivitySummary.model_validate(page.connectivity_summary),
    )


def build_personal_model_list_response(page: ModelListPageResult) -> PersonalModelListResponse:
    items = [PersonalModelResponse.from_gateway_model(row) for row in page.items]
    envelope = build_page(
        items=items,
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )
    return PersonalModelListResponse(
        **envelope.model_dump(),
        connectivity_summary=ModelConnectivitySummary.model_validate(page.connectivity_summary),
    )


def build_paginated_selector_models(
    items: list[dict[str, object]],
    *,
    total: int,
    page: int,
    page_size: int,
) -> PaginatedSelectorModels:
    envelope = build_page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return PaginatedSelectorModels.model_validate(envelope.model_dump())


__all__ = [
    "build_gateway_model_list_response",
    "build_paginated_selector_models",
    "build_personal_model_list_response",
]
