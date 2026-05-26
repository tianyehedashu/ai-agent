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
    parse_registry_ability_filter,
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
    type: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=50,
            description="能力筛选（model_types 或主 capability，与 /models/available 的 type 一致）",
        ),
    ] = None,
    capability: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=50,
            deprecated=True,
            description="已弃用，请用 type；未传 type 时作兼容回退",
        ),
    ] = None,
    enabled: bool | None = None,
) -> ModelListQuery:
    ability = parse_registry_ability_filter(type)
    if ability is None and capability is not None:
        ability = parse_registry_ability_filter(capability)
    return ModelListQuery(
        page_params=PageParams(page=page, page_size=page_size),
        q=q,
        connectivity=ModelListConnectivityFilter(connectivity),
        sort=ModelListSortField(sort),
        order=ModelListSortOrder(order),
        provider=provider,
        credential_id=credential_id,
        ability=ability,
        capability=capability if ability is None else None,
        enabled=enabled,
    )


ModelListQueryDep = Annotated[ModelListQuery, Depends(parse_model_list_query)]

__all__ = ["ModelListQueryDep", "parse_model_list_query"]
