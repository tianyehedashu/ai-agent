"""Gateway application startup and shutdown hooks。

启动期默认仅做 **Router 预热** 与 **后台任务调度**：

- 内置 ``litellm.model_cost`` 在 ``import litellm`` 时已就绪；
- 每次代理调用经 ``attach_downstream_pricing_metadata`` 把上下游单价注入 ``metadata``，
  ``upstream_cost_resolver`` 优先读 metadata，DB 价目无需启动期全量重注册；
- DB 上游行的注册通过 **管理面写入路径** 增量执行（见 ``pricing_writes.py``），
  或通过 ``gateway_catalog_sync_on_startup=true`` 在显式目录维护时一并完成。
"""

from __future__ import annotations

from fastapi import FastAPI

from bootstrap.config import settings
from domains.gateway.application.gateway_catalog_maintenance import (
    log_gateway_catalog_maintenance_report,
    run_gateway_catalog_maintenance,
)
from domains.gateway.infrastructure.router_singleton import get_router, reload_router
from libs.db.database import get_session_factory
from utils.logging import get_logger

logger = get_logger(__name__)


async def run_gateway_startup(app: FastAPI) -> None:
    """Gateway catalog maintenance (optional), router warm-up, and background jobs."""
    try:
        from domains.gateway.application.jobs import schedule_gateway_jobs

        gw_factory = get_session_factory()
        async with gw_factory() as session:
            if settings.gateway_catalog_sync_on_startup:
                try:
                    report = await run_gateway_catalog_maintenance(session, settings=settings)
                    log_gateway_catalog_maintenance_report(report)
                    await session.commit()
                    await reload_router(session)
                except Exception as exc:
                    logger.warning(
                        "Gateway catalog startup maintenance failed: %s",
                        exc,
                        exc_info=True,
                    )

            await get_router(session)

        schedule_gateway_jobs(app)
        logger.info("AI Gateway initialized: Router + background jobs scheduled")
    except Exception as e:
        logger.warning("Failed to initialize AI Gateway: %s", e)


async def run_gateway_shutdown(_app: FastAPI) -> None:
    """Gateway deferred tasks and related teardown."""
    from domains.gateway.application.proxy_deferred_tasks import shutdown_proxy_deferred_tasks

    await shutdown_proxy_deferred_tasks()
