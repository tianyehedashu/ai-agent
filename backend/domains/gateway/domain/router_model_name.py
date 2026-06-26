"""LiteLLM Router ``model_name`` 编解码（纯函数，无 ORM 依赖）。"""

from __future__ import annotations

import uuid

ROUTER_TEAM_PREFIX = "gw/t/"
ROUTER_SYS_PREFIX = "gw/s/"

# 派生 Router deployment 行 id 的命名空间（稳定、与业务 UUID 隔离）。
_ROUTER_DEPLOYMENT_ID_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00cf4fc964ff")


def router_deployment_row_id(model_name: str, gateway_model_id: uuid.UUID) -> str:
    """Router deployment 行的稳定唯一 id（供 LiteLLM 路由/cooldown/负载均衡）。

    同一 ``GatewayModel`` 会在多个 ``model_name``（直连 / owner 路由 / 各消费团队委派）
    中各注册一行；LiteLLM 要求 ``model_info.id`` 全局唯一，否则部署表/cooldown/统计互相
    覆盖、跨团队串台。以 ``(model_name, gateway_model_id)`` 派生即保证唯一又跨 reload 稳定。
    """
    return str(uuid.uuid5(_ROUTER_DEPLOYMENT_ID_NS, f"{model_name}|{gateway_model_id}"))


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


def is_router_encoded_model_name(value: str) -> bool:
    """是否为 Gateway Router 编码后的 ``model_name``（``gw/t/`` 或 ``gw/s/`` 前缀）。"""
    stripped = value.strip()
    return stripped.startswith(ROUTER_TEAM_PREFIX) or stripped.startswith(ROUTER_SYS_PREFIX)


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
    "is_router_encoded_model_name",
    "router_deployment_row_id",
]
