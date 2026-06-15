"""Team-scoped Gateway management routes (``/teams/{team_id}/*``)."""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    alerts,
    budgets,
    credentials,
    dashboard,
    features,
    logs,
    models,
    plans,
    pricing,
    quota_rules,
    routes,
    virtual_key_grants,
    virtual_keys,
)

router = APIRouter(prefix="/teams/{team_id}")

router.include_router(virtual_keys.router)
router.include_router(virtual_key_grants.router)
router.include_router(credentials.router)
router.include_router(models.router)
router.include_router(routes.router)
router.include_router(budgets.router)
router.include_router(quota_rules.router)
router.include_router(logs.router)
router.include_router(dashboard.router)
router.include_router(alerts.router)
router.include_router(plans.router)
router.include_router(pricing.router)
router.include_router(features.router)

__all__ = ["router"]
