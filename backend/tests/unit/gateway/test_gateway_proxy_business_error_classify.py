"""``classify_proxy_use_case_business_error`` 单测。"""

from __future__ import annotations

from fastapi import status

from domains.gateway.domain.errors import ModelNotAllowedError
from domains.gateway.presentation.gateway_proxy_business_error_classify import (
    classify_proxy_use_case_business_error,
)


def test_classify_model_not_allowed() -> None:
    biz = classify_proxy_use_case_business_error(ModelNotAllowedError("gpt-99"))
    assert biz is not None
    assert biz.http_status == status.HTTP_400_BAD_REQUEST
    assert biz.openai_error_type == "model_not_allowed"
    assert biz.anthropic_error_type == "invalid_request_error"


def test_classify_unknown_returns_none() -> None:
    assert classify_proxy_use_case_business_error(RuntimeError("x")) is None
