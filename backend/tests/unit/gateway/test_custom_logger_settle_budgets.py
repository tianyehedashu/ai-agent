"""custom_logger._settle_budgets 在非 success 状态下释放 Phase2 预扣。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from domains.gateway.domain.types import RequestStatus
from domains.gateway.infrastructure.callbacks.custom_logger import _settle_budgets


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        RequestStatus.FAILED.value,
        RequestStatus.BUDGET_EXCEEDED.value,
        RequestStatus.RATE_LIMITED.value,
        RequestStatus.GUARDRAIL_BLOCKED.value,
    ],
)
async def test_settle_budgets_releases_phase2_on_non_success(status: str) -> None:
    metadata = {"gateway_user_id": "00000000-0000-4000-8000-000000000001"}
    release = AsyncMock()
    with patch(
        "domains.gateway.application.budget_deployment_check.release_user_credential_budget_from_metadata",
        release,
    ):
        await _settle_budgets(
            status=status,
            metadata=metadata,
            cost_usd=Decimal("0"),
            input_tokens=0,
            output_tokens=0,
            request_id_str="req-1",
            route_name=None,
            user_id=None,
            cred_id=None,
            deploy_name=None,
        )
    release.assert_awaited_once_with(metadata)


@pytest.mark.asyncio
async def test_settle_budgets_success_does_not_release_phase2() -> None:
    metadata = {"gateway_user_id": "00000000-0000-4000-8000-000000000001"}
    release = AsyncMock()
    with patch(
        "domains.gateway.application.budget_deployment_check.release_user_credential_budget_from_metadata",
        release,
    ):
        await _settle_budgets(
            status=RequestStatus.SUCCESS.value,
            metadata=metadata,
            cost_usd=Decimal("0"),
            input_tokens=0,
            output_tokens=0,
            request_id_str="req-1",
            route_name=None,
            user_id=None,
            cred_id=None,
            deploy_name=None,
        )
    release.assert_not_awaited()
