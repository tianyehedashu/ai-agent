"""请求日志 API 投影（按角色遮罩上游成本）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.inspection import inspect as sa_inspect

from domains.gateway.application.pricing.pricing_catalog_reads import is_pricing_admin
from domains.tenancy.domain.management_context import ManagementTeamContext

_MEMBER_PRICING_SNAPSHOT_KEYS = frozenset(
    {
        "response_cost",
        "downstream_revenue_usd",
        "display_currency",
        "fx_rate_used",
        "hit_chain",
        "gateway_model_id",
    }
)


def _mask_pricing_snapshot(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {k: v for k, v in snapshot.items() if k in _MEMBER_PRICING_SNAPSHOT_KEYS}


def _orm_row_to_dict(record: object) -> dict[str, Any]:
    """从 ORM 已加载列构建 dict，避免 async 会话下 getattr 触发隐式 IO。"""
    state = sa_inspect(record, raiseerr=True)
    orm_mapper = state.mapper
    if orm_mapper is None:
        raise TypeError("record is not a mapped ORM instance")
    loaded = state.dict
    return {attr.key: loaded[attr.key] for attr in orm_mapper.column_attrs if attr.key in loaded}


def request_log_to_dict(record: object, team: ManagementTeamContext) -> dict[str, Any]:
    """ORM → dict，成员侧隐藏 ``cost_usd`` 与上游定价快照。"""
    data = _orm_row_to_dict(record)
    if "tenant_id" in data and "team_id" not in data:
        data["team_id"] = data["tenant_id"]
    if is_pricing_admin(team):
        return data
    data["cost_usd"] = Decimal("0")
    if data.get("pricing_snapshot") is not None:
        data["pricing_snapshot"] = _mask_pricing_snapshot(data["pricing_snapshot"])
    snap = data.get("pricing_snapshot")
    if isinstance(snap, dict):
        snap.pop("upstream_cost_usd", None)
        snap.pop("custom_pricing", None)
        snap.pop("model_map_information", None)
    return data


__all__ = ["request_log_to_dict"]
