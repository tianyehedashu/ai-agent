"""RFC 7807 Problem Details + 项目扩展（``code`` / ``errors`` / ``extra``）。

规范真源：docs/API_RESPONSE.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from libs.exceptions import AIAgentError
from libs.exceptions.base import HttpMappableDomainError
from libs.exceptions.codes import INTERNAL_ERROR

if TYPE_CHECKING:
    from collections.abc import Mapping

ERROR_TYPE_BASE_URL = "https://ai-agent.local/errors/"


class FieldErrorItem(BaseModel):
    loc: list[str | int] = Field(default_factory=list)
    msg: str
    type: str


class ProblemDetails(BaseModel):
    """RFC 7807 + 项目扩展。"""

    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str | None = None
    errors: list[FieldErrorItem] | None = None
    extra: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ProblemContext:
    status_code: int
    detail: str
    title: str
    code: str | None = None
    extra: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    errors: list[FieldErrorItem] | None = None


def error_type_uri(code: str | None) -> str:
    slug = (code or INTERNAL_ERROR).lower().replace("_", "-")
    return f"{ERROR_TYPE_BASE_URL}{slug}"


def default_title_for_status(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "Bad request",
        status.HTTP_401_UNAUTHORIZED: "Unauthorized",
        status.HTTP_403_FORBIDDEN: "Forbidden",
        status.HTTP_404_NOT_FOUND: "Resource not found",
        status.HTTP_409_CONFLICT: "Conflict",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "Validation failed",
        status.HTTP_429_TOO_MANY_REQUESTS: "Rate limit exceeded",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error",
        status.HTTP_502_BAD_GATEWAY: "External service error",
    }.get(status_code, "Error")


def problem_details_from_context(
    ctx: ProblemContext,
    *,
    instance: str | None = None,
) -> ProblemDetails:
    return ProblemDetails(
        type=error_type_uri(ctx.code),
        title=ctx.title,
        status=ctx.status_code,
        detail=ctx.detail,
        instance=instance,
        code=ctx.code,
        errors=ctx.errors,
        extra=ctx.extra or None,
    )


def json_response_from_context(
    ctx: ProblemContext,
    *,
    instance: str | None = None,
) -> JSONResponse:
    body = problem_details_from_context(ctx, instance=instance)
    return JSONResponse(
        status_code=ctx.status_code,
        content=body.model_dump(exclude_none=True),
        headers=ctx.headers,
    )


def problem_response_from_agent_error(
    request: Request,
    exc: AIAgentError,
    status_code: int,
    *,
    title: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    ctx = ProblemContext(
        status_code=status_code,
        detail=exc.message,
        title=title or default_title_for_status(status_code),
        code=exc.code,
        extra=exc.details or None,
        headers=dict(headers) if headers else None,
    )
    return json_response_from_context(ctx, instance=str(request.url.path))


def field_errors_from_request_validation(exc: RequestValidationError) -> list[FieldErrorItem]:
    items: list[FieldErrorItem] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        loc_list: list[str | int] = []
        for part in loc:
            if isinstance(part, (str, int)):
                loc_list.append(part)
            else:
                loc_list.append(str(part))
        items.append(
            FieldErrorItem(
                loc=loc_list,
                msg=str(err.get("msg", "")),
                type=str(err.get("type", "value_error")),
            )
        )
    return items


def problem_response_from_request_validation(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = field_errors_from_request_validation(exc)
    detail = errors[0].msg if len(errors) == 1 else "Validation failed"
    ctx = ProblemContext(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail,
        title="Validation failed",
        code="VALIDATION_ERROR",
        errors=errors,
    )
    return json_response_from_context(ctx, instance=str(request.url.path))


def problem_response_from_http_mappable(
    request: Request,
    exc: HttpMappableDomainError,
) -> JSONResponse:
    from domains.gateway.presentation.http_error_map import (  # pylint: disable=import-outside-toplevel
        problem_context_from_gateway_domain,
    )

    ctx = problem_context_from_gateway_domain(exc)
    return json_response_from_context(ctx, instance=str(request.url.path))


def problem_response_internal(
    request: Request,
    *,
    detail: str = "Internal server error",
    code: str = INTERNAL_ERROR,
) -> JSONResponse:
    ctx = ProblemContext(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
        title=default_title_for_status(status.HTTP_500_INTERNAL_SERVER_ERROR),
        code=code,
    )
    return json_response_from_context(ctx, instance=str(request.url.path))


__all__ = [
    "ERROR_TYPE_BASE_URL",
    "FieldErrorItem",
    "ProblemContext",
    "ProblemDetails",
    "default_title_for_status",
    "error_type_uri",
    "field_errors_from_request_validation",
    "json_response_from_context",
    "problem_details_from_context",
    "problem_response_from_agent_error",
    "problem_response_from_http_mappable",
    "problem_response_from_request_validation",
    "problem_response_internal",
]
