"""Deprecated: 请使用 ``libs.iam.permission_context``。"""

from __future__ import annotations

import warnings

warnings.warn(
    "libs.db.permission_context is deprecated; import from libs.iam.permission_context",
    DeprecationWarning,
    stacklevel=2,
)

from libs.iam.permission_context import (
    PermissionContext,
    clear_permission_context,
    ensure_tenant_in_team_ids,
    get_permission_context,
    merge_team_into_permission_context,
    set_permission_context,
)

__all__ = [
    "PermissionContext",
    "clear_permission_context",
    "ensure_tenant_in_team_ids",
    "get_permission_context",
    "merge_team_into_permission_context",
    "set_permission_context",
]
