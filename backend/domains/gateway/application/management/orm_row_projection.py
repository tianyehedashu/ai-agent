"""ORM 行 → dict 投影（application 读 mapper 共用，避免 presentation 依赖 infrastructure）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.inspection import inspect as sa_inspect


def orm_row_to_dict(record: object) -> dict[str, Any]:
    """从 ORM 已加载列构建 dict，避免 async 会话下 getattr 触发隐式 IO。"""
    state = sa_inspect(record, raiseerr=True)
    orm_mapper = state.mapper
    if orm_mapper is None:
        raise TypeError("record is not a mapped ORM instance")
    loaded = state.dict
    return {attr.key: loaded[attr.key] for attr in orm_mapper.column_attrs if attr.key in loaded}


def tenant_scoped_orm_dict(record: object) -> dict[str, Any]:
    """ORM → dict；存在 ``tenant_id`` 时同步 ``team_id``。"""
    data = orm_row_to_dict(record)
    if "tenant_id" in data and data.get("tenant_id") is not None:
        data["team_id"] = data["tenant_id"]
    return data


__all__ = ["orm_row_to_dict", "tenant_scoped_orm_dict"]
