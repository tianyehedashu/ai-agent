"""内部 Gateway 调用时的「有效用户」解析（注册用户 / 委派 UUID）。"""

from __future__ import annotations

import uuid

from bootstrap.config import settings
from libs.db.permission_context import get_permission_context


def resolve_internal_gateway_user_id() -> uuid.UUID | None:
    """解析可写入 Gateway 归因的 user_id。

    优先级：
    1. 当前 PermissionContext 中的注册用户 ``user_id``；
    2. 配置 ``gateway_internal_proxy_delegate_user_id``（后台任务、worker、
       或希望将匿名/无上下文流量归到固定账号时使用）。

    若两者皆无则返回 ``None``，调用方应直连 LiteLLM（或按 fail_closed 策略失败）。
    """
    ctx = get_permission_context()
    if ctx is not None and isinstance(ctx.user_id, uuid.UUID):
        return ctx.user_id
    delegate = settings.gateway_internal_proxy_delegate_user_id
    if delegate is not None:
        return delegate
    return None
