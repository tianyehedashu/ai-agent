"""LiteLLM Router ``model_name`` 编解码（纯函数，无 ORM 依赖）。"""

from __future__ import annotations

import uuid

ROUTER_TEAM_PREFIX = "gw/t/"
ROUTER_SYS_PREFIX = "gw/s/"


def deployment_scope_team_id(row: object) -> uuid.UUID | None:
    """Router deployment 作用域：系统级行返回 ``None``（``gw/s/``），租户行返回 ``tenant_id``。"""
    tid = getattr(row, "tenant_id", None)
    return tid if isinstance(tid, uuid.UUID) else None


def encode_router_model_name(team_id: uuid.UUID | None, client_name: str) -> str:
    """将客户端 ``model`` 名编码为 Router ``model_list`` 中的 ``model_name``。"""
    name = client_name.strip()
    if not name:
        return name
    if name.startswith(ROUTER_TEAM_PREFIX) or name.startswith(ROUTER_SYS_PREFIX):
        return name
    if team_id is not None:
        return f"{ROUTER_TEAM_PREFIX}{team_id}/{name}"
    return f"{ROUTER_SYS_PREFIX}{name}"


def decode_router_model_name(router_name: str) -> tuple[uuid.UUID | None, str] | None:
    """解析编码后的 Router ``model_name``；非本方案编码则返回 ``None``。"""
    if router_name.startswith(ROUTER_TEAM_PREFIX):
        rest = router_name[len(ROUTER_TEAM_PREFIX) :]
        team_part, _, client = rest.partition("/")
        if not team_part or not client:
            return None
        try:
            return uuid.UUID(team_part), client
        except ValueError:
            return None
    if router_name.startswith(ROUTER_SYS_PREFIX):
        return None, router_name[len(ROUTER_SYS_PREFIX) :]
    return None


__all__ = [
    "ROUTER_SYS_PREFIX",
    "ROUTER_TEAM_PREFIX",
    "decode_router_model_name",
    "deployment_scope_team_id",
    "encode_router_model_name",
]
