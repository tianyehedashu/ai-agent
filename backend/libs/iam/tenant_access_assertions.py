"""租户访问断言——将 ``check_tenant_access`` 核心规则下沉到 IAM 层（纯函数，无 FastAPI 依赖）。"""

from __future__ import annotations

from uuid import UUID

from libs.exceptions import PermissionDeniedError
from libs.iam.data_scope_policy import (
    DataAction,
    DataResource,
    enforce_data_scope,
)
from libs.iam.permission_context import get_permission_context

__all__ = [
    "assert_tenant_access",
    "assert_tenant_access_or_public",
]


def assert_tenant_access(
    resource_tenant_id: UUID,
    role: str,
    resource_name: str = "Resource",
) -> None:
    """显式校验 actor 对目标租户资源的 READ 访问权；admin 旁路。

    与 ``check_tenant_access`` 语义一致，但脱离 ``CurrentUser`` 等 Presentation 类型，
    便于在 Application / Domain 层直接调用。
    """
    if role == "admin":
        return

    ctx = get_permission_context()
    if ctx is None:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )
    allowed = enforce_data_scope(
        ctx,
        DataResource(kind=resource_name, tenant_id=resource_tenant_id),
        DataAction.READ,
    )
    if not allowed:
        raise PermissionDeniedError(
            message=f"You don't have permission to access this {resource_name.lower()}",
            resource=resource_name,
        )


def assert_tenant_access_or_public(
    resource_tenant_id: UUID,
    role: str,
    is_public: bool,
    resource_name: str = "Resource",
) -> None:
    """公开资源跳过 tenant 检查，否则委托 ``assert_tenant_access``"""
    if is_public:
        return
    assert_tenant_access(resource_tenant_id, role, resource_name)
