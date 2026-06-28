"""Gateway 请求日志 probe 分页 response 单测。"""

from __future__ import annotations

import uuid

from domains.gateway.presentation.schemas.common import RequestLogResponse
from domains.gateway.presentation.schemas.gateway_log_list_response import (
    build_request_log_list_response,
)


def _log_item() -> RequestLogResponse:
    return RequestLogResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "created_at": "2026-06-22T10:00:00+00:00",
            "team_id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "vkey_id": None,
            "credential_id": None,
            "credential_name_snapshot": None,
            "capability": "chat",
            "route_name": "gpt-4",
            "real_model": "gpt-4",
            "provider": "openai",
            "status": "success",
            "error_code": None,
            "input_tokens": 1,
            "output_tokens": 1,
            "cached_tokens": 0,
            "cache_creation_tokens": 0,
            "cost_usd": "0.001",
            "latency_ms": 100,
            "cache_hit": False,
            "fallback_chain": [],
            "request_id": "req-1",
            "user_email_snapshot": None,
            "vkey_name_snapshot": None,
            "client_type": "unknown",
        }
    )


def test_build_request_log_list_response_marks_inexact_total_when_has_next() -> None:
    items = [_log_item() for _ in range(10)]
    resp = build_request_log_list_response(
        items=items,
        page=1,
        page_size=10,
        has_next=True,
    )
    assert resp.total == 10
    assert resp.total_exact is False
    assert resp.has_next is True
    assert resp.has_prev is False


def test_build_request_log_list_response_exact_total_on_last_page() -> None:
    items = [_log_item() for _ in range(3)]
    resp = build_request_log_list_response(
        items=items,
        page=2,
        page_size=10,
        has_next=False,
    )
    assert resp.total == 13
    assert resp.total_exact is True
    assert resp.has_next is False
    assert resp.has_prev is True
