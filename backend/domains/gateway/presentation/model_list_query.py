"""Gateway 模型列表 HTTP query 解析。"""

from __future__ import annotations

from typing import Annotated, Literal
import uuid

from fastapi import Depends, Query

from domains.gateway.application.model_list_pipeline import ModelListQuery
from domains.gateway.domain.policies.model_list_policy import (
    ModelListConnectivityFilter,
    ModelListSortField,
    ModelListSortOrder,
)
from libs.api.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageParams


def parse_model_list_query(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    connectivity: Annotated[
        Literal["all", "success", "failed", "unknown"],
        Query(description="连通性健康筛选"),
    ] = "all",
    sort: Annotated[
        Literal["name", "created_at", "provider", "last_tested_at"],
        Query(description="排序字段（可用性 tier 始终优先）"),
    ] = "name",
    order: Annotated[Literal["asc", "desc"], Query()] = "asc",
    provider: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    credential_id: uuid.UUID | None = None,
    capability: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    enabled: bool | None = None,
) -> ModelListQuery:
    return ModelListQuery(
        page_params=PageParams(page=page, page_size=page_size),
        q=q,
        connectivity=ModelListConnectivityFilter(connectivity),
        sort=ModelListSortField(sort),
        order=ModelListSortOrder(order),
        provider=provider,
        credential_id=credential_id,
        capability=capability,
        enabled=enabled,
    )


ModelListQueryDep = Annotated[ModelListQuery, Depends(parse_model_list_query)]

__all__ = ["ModelListQueryDep", "parse_model_list_query"]
