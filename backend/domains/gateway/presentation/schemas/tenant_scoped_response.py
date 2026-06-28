"""租户作用域 ORM → API dict 投影（``tenant_id`` 权威，``team_id`` 兼容镜像）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.inspection import inspect as sa_inspect


def _orm_row_to_dict(record: object) -> dict[str, Any]:
    """从 ORM 已加载列构建 dict，避免 async 会话下 getattr 触发隐式 IO。"""
    state = sa_inspect(record, raiseerr=True)
    orm_mapper = state.mapper
    if orm_mapper is None:
        raise TypeError("record is not a mapped ORM instance")
    loaded = state.dict
    return {attr.key: loaded[attr.key] for attr in orm_mapper.column_attrs if attr.key in loaded}


def tenant_scoped_orm_dict(record: object) -> dict[str, Any]:
    """ORM → dict；存在 ``tenant_id`` 时同步 ``team_id``（计费/历史 JSON 兼容）。"""
    data = _orm_row_to_dict(record)
    if "tenant_id" in data and data.get("tenant_id") is not None:
        data["team_id"] = data["tenant_id"]
    return data


def apply_tenant_team_mirror(data: dict[str, Any]) -> dict[str, Any]:
    """对已构建的 dict 补全 ``team_id`` / ``tenant_id`` 镜像。"""
    if "tenant_id" in data and data.get("tenant_id") is not None:
        data.setdefault("team_id", data["tenant_id"])
    elif "team_id" in data and data.get("team_id") is not None:
        data.setdefault("tenant_id", data["team_id"])
    return data


__all__ = ["apply_tenant_team_mirror", "tenant_scoped_orm_dict"]
