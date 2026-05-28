"""RFC 7807 Problem Details 单元测试。"""

from __future__ import annotations

from fastapi import Request, status
import pytest

from libs.api.problem_details import (
    error_type_uri,
    field_errors_from_request_validation,
    problem_response_from_agent_error,
    problem_response_internal,
)
from libs.exceptions import NotFoundError, ValidationError
from libs.exceptions.codes import NOT_FOUND, VALIDATION_ERROR


def _fake_request(path: str = "/api/v1/test") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "scheme": "http",
        "root_path": "",
    }
    return Request(scope)


@pytest.mark.unit
def test_error_type_uri() -> None:
    assert error_type_uri(NOT_FOUND) == "https://ai-agent.local/errors/not-found"
    assert error_type_uri(None).endswith("/internal-error")


@pytest.mark.unit
def test_problem_response_from_agent_error() -> None:
    exc = NotFoundError("Session", "abc")
    response = problem_response_from_agent_error(
        _fake_request("/api/v1/sessions/abc"),
        exc,
        status.HTTP_404_NOT_FOUND,
    )
    body = response.body.decode()
    assert response.status_code == 404
    assert NOT_FOUND in body
    assert "Session not found" in body
    assert '"title"' in body
    assert '"instance"' in body


@pytest.mark.unit
def test_problem_response_internal() -> None:
    response = problem_response_internal(_fake_request())
    payload = response.body.decode()
    assert response.status_code == 500
    assert "INTERNAL_ERROR" in payload


@pytest.mark.unit
def test_validation_error_includes_extra() -> None:
    exc = ValidationError("bad input", details={"field": "name"})
    response = problem_response_from_agent_error(
        _fake_request(),
        exc,
        status.HTTP_400_BAD_REQUEST,
    )
    payload = response.body.decode()
    assert VALIDATION_ERROR in payload
    assert '"extra"' in payload
    assert "name" in payload


@pytest.mark.unit
def test_field_errors_from_request_validation_shape() -> None:
    from fastapi.exceptions import RequestValidationError

    exc = RequestValidationError(
        [
            {
                "type": "missing",
                "loc": ("body", "name"),
                "msg": "Field required",
                "input": {},
            }
        ]
    )
    items = field_errors_from_request_validation(exc)
    assert len(items) == 1
    assert items[0].loc == ["body", "name"]
    assert items[0].msg == "Field required"
