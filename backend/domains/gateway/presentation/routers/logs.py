"""请求日志 (Logs) 子 router。

Stage 2 起，应用层经 ``UsageAxis`` 统一访问仓储，本 router 只负责接收 HTTP
``usage_aggregation``（产品视角，``workspace`` / ``user``）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, Query

from domains.gateway.application.management.log_presentation import request_log_to_dict
from domains.gateway.domain.usage_read_model import (
    USAGE_AGGREGATION_QUERY_DESCRIPTION,
    UsageAggregation,
)
from domains.gateway.presentation.deps import CurrentTeam
from domains.gateway.presentation.gateway_log_list_response import build_request_log_list_response
from domains.gateway.presentation.schemas.common import (
    RequestLogDetailResponse,
    RequestLogListResponse,
    RequestLogResponse,
)
from libs.api.pagination import PageParams, page_query_params
from libs.exceptions import NotFoundError

from ._common import MgmtReads

router = APIRouter()
PageDep = Annotated[PageParams, Depends(page_query_params)]


@router.get("/logs", response_model=RequestLogListResponse)
async def list_logs(
    team: CurrentTeam,
    reads: MgmtReads,
    page: PageDep,
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
    user_id: uuid.UUID | None = None,
    model: str | None = Query(default=None, min_length=1, max_length=200),
    client_type: str | None = Query(default=None, min_length=1, max_length=100),
) -> RequestLogListResponse:
    items, total = await reads.list_request_logs(
        team,
        usage_aggregation=usage_aggregation,
        page=page.page,
        page_size=page.page_size,
        start=start,
        end=end,
        status_filter=status_filter,
        capability=capability,
        vkey_id=vkey_id,
        credential_id=credential_id,
        user_id=user_id,
        model=model.strip() if model else None,
        client_type=client_type.strip() if client_type else None,
    )
    log_items = [RequestLogResponse.model_validate(request_log_to_dict(i, team)) for i in items]
    return build_request_log_list_response(
        items=log_items,
        total=total,
        page=page.page,
        page_size=page.page_size,
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
    record = await reads.get_request_log(team, log_id, usage_aggregation=usage_aggregation)
    if record is None:
        raise NotFoundError("Log")
    return RequestLogDetailResponse.model_validate(request_log_to_dict(record, team))


__all__ = ["router"]
