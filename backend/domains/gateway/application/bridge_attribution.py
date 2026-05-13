"""内部 Gateway 桥接归因（gateway 应用层，供跨域调用方使用）。

术语
----
**Actor（操作者）**
    可写入日志 ``gateway_user_id`` 的注册用户 UUID；来自
    ``resolve_internal_gateway_user_id``（PermissionContext 或委派配置）。

**BillingWorkspace（计费工作区）**
    与 ``gateway_request_logs.team_id``、LiteLLM metadata ``gateway_team_id`` 对齐；
    ``None`` 表示未指定，由 ``GatewayBridge`` 回退为 ``ensure_personal_team(actor)``。

不变量
------
桥接入口在调用本模块前须已保证能解析到 Actor；否则 ``resolve_gateway_bridge_attribution``
会抛出 ``ValueError``。
"""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from domains.gateway.application.internal_bridge_actor import (
    resolve_internal_gateway_team_id,
    resolve_internal_gateway_user_id,
)


@dataclass(frozen=True)
class GatewayBridgeAttribution:
    """单次内部桥接的归因结果（供 ``GatewayCallContext`` 使用）。"""

    actor_user_id: uuid.UUID
    billing_team_id: uuid.UUID | None


def resolve_gateway_bridge_attribution(
    *,
    explicit_billing_team_id: uuid.UUID | None = None,
) -> GatewayBridgeAttribution:
    """解析桥接归因：计费工作区优先级为显式参数 > PermissionContext.team_id > None。

    Args:
        explicit_billing_team_id: 调用方显式指定的计费工作区（通常来自已构造的
            ``GatewayCallContext.team_id``）；一般内部 LLM 路径传 ``None``。
    """
    actor = resolve_internal_gateway_user_id()
    if actor is None:
        msg = "bridge attribution requires resolve_internal_gateway_user_id() to be non-None"
        raise ValueError(msg)
    if explicit_billing_team_id is not None:
        billing: uuid.UUID | None = explicit_billing_team_id
    else:
        billing = resolve_internal_gateway_team_id()
    return GatewayBridgeAttribution(actor_user_id=actor, billing_team_id=billing)


__all__ = ["GatewayBridgeAttribution", "resolve_gateway_bridge_attribution"]
