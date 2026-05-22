"""Entitlement 列表态与模型可调用性（选择器与 GET /v1/models 共用）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.domain.types import EntitlementListStatus, ModelConnectivityStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.entitlement_guard import EntitlementGuard

from domains.gateway.infrastructure.repositories.entitlement_plan_repository import (
    ENTITLEMENT_SCOPE_APIKEY_GRANT,
    ENTITLEMENT_SCOPE_VKEY,
)

# 配额已耗尽且距窗口重置不超过该秒数时，列表态为 ``resetting``（与前端 Badge 一致）
ENTITLEMENT_RESETTING_SOON_SECONDS = 300


def resolve_entitlement_scope(
    *,
    vkey_id: uuid.UUID | None = None,
    apikey_grant_id: uuid.UUID | None = None,
) -> tuple[str | None, uuid.UUID | None]:
    """从入站主体 ID 解析 entitlement 仓储 scope。"""
    if vkey_id is not None:
        return ENTITLEMENT_SCOPE_VKEY, vkey_id
    if apikey_grant_id is not None:
        return ENTITLEMENT_SCOPE_APIKEY_GRANT, apikey_grant_id
    return None, None


def connectivity_status_from_last_test(
    last_test_status: str | None,
) -> ModelConnectivityStatus | None:
    if last_test_status == "success":
        return "success"
    if last_test_status == "failed":
        return "failed"
    return None


def is_connectivity_requestable(last_test_status: str | None) -> bool:
    """连通性探活未失败时方可进入「可用/可请求」目录（与 ``registry_scope=requestable`` 对齐）。"""
    return last_test_status != "failed"


def compute_model_callable(
    *,
    connectivity_status: ModelConnectivityStatus | None,
    entitlement_status: EntitlementListStatus,
) -> bool:
    """是否建议发起代理请求（连通性失败或套餐耗尽/过期为 false）。"""
    if connectivity_status == "failed":
        return False
    return entitlement_status not in ("exhausted", "expired")


async def entitlement_status_by_model_names(
    session: AsyncSession,
    *,
    scope: str | None,
    scope_id: uuid.UUID | None,
    model_names: list[str],
) -> dict[str, EntitlementListStatus]:
    if not model_names:
        return {}
    if scope is None or scope_id is None:
        return dict.fromkeys(model_names, "none")
    from domains.gateway.application.entitlement_guard import build_entitlement_guard_for_session

    guard = build_entitlement_guard_for_session(session)
    return await guard.status_for_models(scope, scope_id, model_names)


async def annotate_items_entitlement_status(
    items: list[dict[str, Any]],
    *,
    guard: EntitlementGuard | None,
    scope: str | None,
    scope_id: uuid.UUID | None,
) -> list[dict[str, Any]]:
    """为选择器条目注入 ``entitlement_status``。"""
    if not items:
        return items
    if guard is None or scope is None or scope_id is None:
        for item in items:
            item.setdefault("entitlement_status", "none")
        return items
    names = [str(item.get("id") or item.get("name") or "") for item in items]
    statuses = await guard.status_for_models(scope, scope_id, names)
    for item, name in zip(items, names, strict=True):
        item["entitlement_status"] = statuses.get(name, "none")
    return items


__all__ = [
    "ENTITLEMENT_RESETTING_SOON_SECONDS",
    "annotate_items_entitlement_status",
    "compute_model_callable",
    "connectivity_status_from_last_test",
    "entitlement_status_by_model_names",
    "is_connectivity_requestable",
    "resolve_entitlement_scope",
]
