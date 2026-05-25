"""分页请求/响应标准 envelope（HTTP 列表 API 共用）。

规范真源：docs/PAGINATION.md
code-check：.cursor/agents/code-rule-check.md §15
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Sequence

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200


class PageParams(BaseModel):
    """1-based 页码分页参数。"""

    page: int = Field(1, ge=1)
    page_size: int = Field(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedListResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=MAX_PAGE_SIZE)
    has_next: bool
    has_prev: bool


def total_pages(total: int, page_size: int) -> int:
    if total <= 0:
        return 1
    return max(1, (total + page_size - 1) // page_size)


def build_page(
    *,
    items: list[T],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedListResponse[T]:
    pages = total_pages(total, page_size)
    safe_page = min(max(1, page), pages)
    return PaginatedListResponse(
        items=items,
        total=total,
        page=safe_page,
        page_size=page_size,
        has_next=safe_page < pages,
        has_prev=safe_page > 1,
    )


def slice_page(
    rows: Sequence[T],
    *,
    page: int,
    page_size: int,
) -> tuple[list[T], int]:
    """内存分页（merge 路径）；返回 (page_items, total)。"""
    total = len(rows)
    if total == 0:
        return [], 0
    offset = (max(1, page) - 1) * page_size
    return list(rows[offset : offset + page_size]), total


def page_query_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "PageParams",
    "PaginatedListResponse",
    "build_page",
    "page_query_params",
    "slice_page",
    "total_pages",
]
