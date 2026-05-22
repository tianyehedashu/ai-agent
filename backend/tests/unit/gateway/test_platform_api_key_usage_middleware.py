"""PlatformApiKeyUsageASGIMiddleware 单测。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from domains.gateway.presentation.platform_api_key_usage_middleware import (
    PLATFORM_API_KEY_USAGE_STATE,
    PlatformApiKeyUsageASGIMiddleware,
    PlatformApiKeyUsageContext,
)


async def _echo_ok(request: Request) -> JSONResponse:
    ctx = PlatformApiKeyUsageContext(
        api_key_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )
    setattr(request.state, PLATFORM_API_KEY_USAGE_STATE, ctx)
    request.scope[PLATFORM_API_KEY_USAGE_STATE] = ctx
    return JSONResponse({"ok": True})


@pytest.mark.asyncio
async def test_middleware_records_platform_api_key_usage() -> None:
    app = PlatformApiKeyUsageASGIMiddleware(
        Starlette(routes=[Route("/", _echo_ok, methods=["GET"])])
    )
    recorded: list[tuple[uuid.UUID, dict[str, object]]] = []

    class FakeAccess:
        async def record_platform_api_key_usage(
            self,
            api_key_id: uuid.UUID,
            *,
            user_id: uuid.UUID,
            endpoint: str,
            method: str,
            ip_address: str | None,
            user_agent: str | None,
            status_code: int,
            response_time_ms: int | None,
        ) -> None:
            recorded.append(
                (
                    api_key_id,
                    {
                        "user_id": user_id,
                        "endpoint": endpoint,
                        "method": method,
                        "status_code": status_code,
                    },
                )
            )

    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("libs.db.database.get_session_factory", return_value=mock_factory),
        patch(
            "domains.gateway.application.gateway_access_factory.build_gateway_access_use_case",
            return_value=FakeAccess(),
        ),
    ):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/", headers={"user-agent": "pytest"})
            assert response.status_code == 200

    assert len(recorded) == 1
    assert recorded[0][1]["method"] == "GET"
    assert recorded[0][1]["status_code"] == 200
    mock_session.commit.assert_awaited_once()
