"""Gateway 管理面访问策略——平台角色相关规则（纯函数，无 IO）。"""

from __future__ import annotations

from domains.identity.domain.rbac import Role
from libs.exceptions import PermissionDeniedError

READ_ONLY_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def assert_gateway_write_allowed(platform_role: str, http_method: str) -> None:
    """Viewer 角色在 Gateway 管理面仅允许读方法；非读方法抛出权限异常。

    从 ``team_dependencies._assert_gateway_not_viewer_write`` 下沉，
    解除对 ``starlette.Request`` 的 Presentation 层依赖。
    """
    if platform_role == Role.VIEWER.value and http_method not in READ_ONLY_HTTP_METHODS:
        raise PermissionDeniedError(
            message="Viewer accounts are read-only on AI Gateway",
            resource="AI Gateway",
        )


__all__ = ["assert_gateway_write_allowed", "READ_ONLY_HTTP_METHODS"]
