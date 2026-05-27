"""Gateway 请求日志分页 response 组装。"""

from __future__ import annotations

from domains.gateway.presentation.schemas.common import RequestLogListResponse, RequestLogResponse
from libs.api.pagination import build_page


def build_request_log_list_response(
    *,
    items: list[RequestLogResponse],
    total: int,
    page: int,
    page_size: int,
) -> RequestLogListResponse:
    envelope = build_page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return RequestLogListResponse(**envelope.model_dump())


__all__ = ["build_request_log_list_response"]
