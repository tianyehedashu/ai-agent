"""Gateway 请求日志分页 response 组装。"""

from __future__ import annotations

from domains.gateway.presentation.schemas.common import RequestLogListResponse, RequestLogResponse


def build_request_log_list_response(
    *,
    items: list[RequestLogResponse],
    page: int,
    page_size: int,
    has_next: bool,
) -> RequestLogListResponse:
    """Probe 分页：不执行 COUNT；末页时 ``total`` 为精确值。"""
    has_prev = page > 1
    item_count = len(items)
    total = (page - 1) * page_size + item_count
    return RequestLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
        has_prev=has_prev,
        total_exact=not has_next,
    )


__all__ = ["build_request_log_list_response"]
