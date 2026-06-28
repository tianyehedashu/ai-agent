"""GatewayModel / SystemGatewayModel ORM → API 投影 dict（application 读 mapper）。"""

from __future__ import annotations

from typing import Any

from domains.gateway.application.management.orm_row_projection import tenant_scoped_orm_dict
from domains.gateway.domain.catalog.model_selection import registry_kind_for_merged_row


def gateway_model_row_to_api_dict(record: object) -> dict[str, Any]:
    """ORM 行 → ``GatewayModelResponse`` 兼容 dict（不含 presentation Schema）。"""
    data = tenant_scoped_orm_dict(record)
    kind = registry_kind_for_merged_row(record)
    data["registry_kind"] = kind
    if kind == "system":
        data["visibility"] = getattr(record, "visibility", None)
    return data


__all__ = ["gateway_model_row_to_api_dict"]
