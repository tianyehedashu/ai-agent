"""Gateway application startup and shutdown hooks."""

from __future__ import annotations

from fastapi import FastAPI

from bootstrap.config import settings
from domains.gateway.application.config_catalog_sync import sync_app_config_gateway_catalog
from domains.gateway.infrastructure.router_singleton import get_router, reload_router
from libs.db.database import get_session_context, get_session_factory
from utils.logging import get_logger

logger = get_logger(__name__)


async def run_gateway_startup(app: FastAPI) -> None:
    """Gateway catalog sync, router warm-up, and background jobs."""
    if settings.gateway_catalog_sync_on_startup:
        try:
            async with get_session_context() as session:
                await sync_app_config_gateway_catalog(session)
                from domains.gateway.application.pricing.pricing_management import (
                    build_pricing_service,
                )

                pricing_svc = build_pricing_service(session)
                await pricing_svc.sync_to_litellm_registry()
                from domains.gateway.application.pricing.upstream_pricing_audit import (
                    audit_upstream_pricing_keys,
                )

                audit = await audit_upstream_pricing_keys(session)
                if audit.models_without_upstream:
                    logger.warning(
                        "Gateway upstream pricing: %d models missing upstream rows (sample: %s)",
                        len(audit.models_without_upstream),
                        audit.models_without_upstream[:5],
                    )
                from domains.gateway.application.route_audit import audit_gateway_routes

                route_report = await audit_gateway_routes(session)
                if route_report.issues:
                    logger.warning(
                        "Gateway route references: %d issues across %d routes (sample: %s)",
                        len(route_report.issues),
                        route_report.total_routes,
                        [
                            (i.virtual_model, i.field, list(i.missing_names))
                            for i in route_report.issues[:5]
                        ],
                    )
                if route_report.cross_team_virtual_model_collisions:
                    logger.warning(
                        "Gateway routes: %d virtual_model names shared across teams "
                        "(Router uses gw/t/{team_id}/ prefix; sample: %s)",
                        len(route_report.cross_team_virtual_model_collisions),
                        [
                            (c.virtual_model, list(c.team_ids))
                            for c in route_report.cross_team_virtual_model_collisions[:5]
                        ],
                    )
                if route_report.virtual_model_shadowed_by_model:
                    logger.info(
                        "Gateway routes shadowed by GatewayModel rows: %d sample=%s "
                        "(GatewayModel.name 命中时优先于路由调度)",
                        len(route_report.virtual_model_shadowed_by_model),
                        route_report.virtual_model_shadowed_by_model[:5],
                    )
                await session.commit()
                await reload_router(session)
        except Exception as exc:
            logger.warning("Gateway catalog startup sync failed: %s", exc, exc_info=True)

    try:
        from domains.gateway.application.jobs import schedule_gateway_jobs

        gw_factory = get_session_factory()
        async with gw_factory() as db:
            await get_router(db)
        schedule_gateway_jobs(app)
        logger.info("AI Gateway initialized: Router + background jobs scheduled")
    except Exception as e:
        logger.warning("Failed to initialize AI Gateway: %s", e)


async def run_gateway_shutdown(_app: FastAPI) -> None:
    """Gateway deferred tasks and related teardown."""
    from domains.gateway.application.proxy_deferred_tasks import shutdown_proxy_deferred_tasks

    await shutdown_proxy_deferred_tasks()
