"""Gateway 目录种子同步后的统一维护管道（catalog、LiteLLM 价目、审计）。

供应用启动（``gateway_catalog_sync_on_startup``）与管理 API
``POST /catalog/reload-from-config`` 共用，避免行为漂移。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.config import Settings
from domains.gateway.application.config_catalog_sync import sync_gateway_catalog_from_seed
from domains.gateway.application.credential_env_audit import log_config_managed_api_base_drift
from domains.gateway.application.pricing.pricing_management import build_pricing_service
from domains.gateway.application.pricing.upstream_pricing_audit import (
    UpstreamPricingAuditReport,
    audit_upstream_pricing_keys,
)
from domains.gateway.application.route_audit import RouteAuditReport, audit_gateway_routes
from utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GatewayCatalogMaintenanceReport:
    """目录维护管道执行结果（供日志与 API 返回）。"""

    catalog_stats: dict[str, int]
    litellm_registered: int
    upstream_audit: UpstreamPricingAuditReport
    route_audit: RouteAuditReport

    def to_api_dict(self) -> dict[str, Any]:
        """管理 API 响应：catalog 统计 + 价目注册数 + 审计摘要。"""
        return {
            **self.catalog_stats,
            "litellm_registered": self.litellm_registered,
            "upstream_audit": self.upstream_audit.to_dict(),
            "route_audit": {
                "total_routes": self.route_audit.total_routes,
                "issue_count": len(self.route_audit.issues),
                "cross_team_collision_count": len(
                    self.route_audit.cross_team_virtual_model_collisions
                ),
                "shadowed_count": len(self.route_audit.virtual_model_shadowed_by_model),
            },
        }


async def run_gateway_catalog_maintenance(
    session: AsyncSession,
    *,
    settings: Settings,
    seed_path: Path | None = None,
) -> GatewayCatalogMaintenanceReport:
    """从 seed 幂等同步目录，注册 LiteLLM 上游价，并运行只读审计（不 commit）。"""
    catalog_stats = await sync_gateway_catalog_from_seed(session, seed_path=seed_path)
    pricing_svc = build_pricing_service(session)
    litellm_registered = await pricing_svc.sync_to_litellm_registry()
    upstream_audit = await audit_upstream_pricing_keys(session)
    route_audit = await audit_gateway_routes(session)
    await log_config_managed_api_base_drift(session, settings)
    return GatewayCatalogMaintenanceReport(
        catalog_stats=catalog_stats,
        litellm_registered=litellm_registered,
        upstream_audit=upstream_audit,
        route_audit=route_audit,
    )


def log_gateway_catalog_maintenance_report(report: GatewayCatalogMaintenanceReport) -> None:
    """将维护结果写入应用日志（warning/info）。"""
    logger.info(
        "Gateway catalog maintenance finished: upserted=%s disabled=%s skipped_no_credential=%s "
        "litellm_registered=%s",
        report.catalog_stats.get("upserted"),
        report.catalog_stats.get("disabled"),
        report.catalog_stats.get("skipped_no_credential"),
        report.litellm_registered,
    )
    if report.upstream_audit.models_without_upstream:
        logger.warning(
            "Gateway upstream pricing: %d models missing upstream rows (sample: %s)",
            len(report.upstream_audit.models_without_upstream),
            report.upstream_audit.models_without_upstream[:5],
        )
    if report.route_audit.issues:
        logger.warning(
            "Gateway route references: %d issues across %d routes (sample: %s)",
            len(report.route_audit.issues),
            report.route_audit.total_routes,
            [
                (i.virtual_model, i.field, list(i.missing_names))
                for i in report.route_audit.issues[:5]
            ],
        )
    if report.route_audit.cross_team_virtual_model_collisions:
        logger.warning(
            "Gateway routes: %d virtual_model names shared across teams "
            "(Router uses gw/t/{team_id}/ prefix; sample: %s)",
            len(report.route_audit.cross_team_virtual_model_collisions),
            [
                (c.virtual_model, list(c.team_ids))
                for c in report.route_audit.cross_team_virtual_model_collisions[:5]
            ],
        )
    if report.route_audit.virtual_model_shadowed_by_model:
        logger.info(
            "Gateway routes shadowed by GatewayModel rows: %d sample=%s "
            "(GatewayModel.name 命中时优先于路由调度)",
            len(report.route_audit.virtual_model_shadowed_by_model),
            report.route_audit.virtual_model_shadowed_by_model[:5],
        )


__all__ = [
    "GatewayCatalogMaintenanceReport",
    "log_gateway_catalog_maintenance_report",
    "run_gateway_catalog_maintenance",
]
