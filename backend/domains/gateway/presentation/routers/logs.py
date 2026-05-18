"""请求日志 (Logs) 子 router。

Stage 2 起，应用层经 ``UsageAxis`` 统一访问仓储，本 router 只负责接收 HTTP
``usage_aggregation``（产品视角，``workspace`` / ``user``）。
"""

from __future__ import annotations

from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from domains.gateway.domain.usage_read_model import (
    USAGE_AGGREGATION_QUERY_DESCRIPTION,
    UsageAggregation,
)
from domains.gateway.presentation.deps import CurrentTeam
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.gateway.presentation.schemas.common import (
    RequestLogDetailResponse,
    RequestLogListResponse,
    RequestLogResponse,
)
from libs.exceptions import HttpMappableDomainError

from ._common import MgmtReads

router = APIRouter()


@router.get("/logs", response_model=RequestLogListResponse)
async def list_logs(
    team: CurrentTeam,
    reads: MgmtReads,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=USAGE_AGGREGATION_QUERY_DESCRIPTION,
    ),
    start: datetime | None = None,
    end: datetime | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    capability: str | None = None,
    vkey_id: uuid.UUID | None = None,
    credential_id: uuid.UUID | None = None,
) -> RequestLogListResponse:
    items, total = await reads.list_request_logs(
        team,
        usage_aggregation=usage_aggregation,
        page=page,
        page_size=page_size,
        start=start,
        end=end,
        status_filter=status_filter,
        capability=capability,
        vkey_id=vkey_id,
        credential_id=credential_id,
    )
    return RequestLogListResponse(
        items=[RequestLogResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/{log_id}", response_model=RequestLogDetailResponse)
async def get_log_detail(
    log_id: uuid.UUID,
    team: CurrentTeam,
    reads: MgmtReads,
    usage_aggregation: UsageAggregation = Query(
        UsageAggregation.WORKSPACE,
        description=USAGE_AGGREGATION_QUERY_DESCRIPTION,
    ),
) -> RequestLogDetailResponse:
    try:
        record = await reads.get_request_log(team, log_id, usage_aggregation=usage_aggregation)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Log not found")
    return RequestLogDetailResponse.model_validate(record)


__all__ = ["router"]
