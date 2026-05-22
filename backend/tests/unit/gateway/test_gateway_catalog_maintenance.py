"""gateway_catalog_maintenance 管道单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from domains.gateway.application.gateway_catalog_maintenance import (
    GatewayCatalogMaintenanceReport,
    run_gateway_catalog_maintenance,
)
from domains.gateway.application.pricing.upstream_pricing_audit import UpstreamPricingAuditReport
from domains.gateway.application.route_audit import RouteAuditReport


@pytest.mark.asyncio
async def test_run_gateway_catalog_maintenance_orchestrates_steps() -> None:
    session = AsyncMock()
    catalog_stats = {"upserted": 2, "disabled": 0, "skipped_no_credential": 1}
    upstream = UpstreamPricingAuditReport(
        models_without_upstream=[],
        upstream_without_model=[],
        registered_upstream_keys=3,
    )
    routes = RouteAuditReport(total_routes=0)

    with (
        patch(
            "domains.gateway.application.gateway_catalog_maintenance.sync_gateway_catalog_from_seed",
            new_callable=AsyncMock,
            return_value=catalog_stats,
        ) as sync_seed,
        patch(
            "domains.gateway.application.gateway_catalog_maintenance.build_pricing_service",
        ) as build_pricing,
        patch(
            "domains.gateway.application.gateway_catalog_maintenance.audit_upstream_pricing_keys",
            new_callable=AsyncMock,
            return_value=upstream,
        ),
        patch(
            "domains.gateway.application.gateway_catalog_maintenance.audit_gateway_routes",
            new_callable=AsyncMock,
            return_value=routes,
        ),
        patch(
            "domains.gateway.application.gateway_catalog_maintenance.log_config_managed_api_base_drift",
            new_callable=AsyncMock,
        ) as drift,
    ):
        pricing_svc = AsyncMock()
        pricing_svc.sync_to_litellm_registry = AsyncMock(return_value=5)
        build_pricing.return_value = pricing_svc

        from bootstrap.config import settings

        report = await run_gateway_catalog_maintenance(session, settings=settings)

    sync_seed.assert_awaited_once_with(session, seed_path=None)
    pricing_svc.sync_to_litellm_registry.assert_awaited_once()
    drift.assert_awaited_once()
    assert isinstance(report, GatewayCatalogMaintenanceReport)
    assert report.catalog_stats == catalog_stats
    assert report.litellm_registered == 5
    assert report.to_api_dict()["litellm_registered"] == 5
