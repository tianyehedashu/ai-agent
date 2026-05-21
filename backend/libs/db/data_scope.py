"""Deprecated: 策略见 ``libs.iam.data_scope_policy``，SQL 见 ``libs.db.data_scope_clause``。"""

from __future__ import annotations

import warnings

warnings.warn(
    "libs.db.data_scope is deprecated; use libs.iam.data_scope_policy and "
    "libs.db.data_scope_clause",
    DeprecationWarning,
    stacklevel=2,
)

from libs.db.data_scope_clause import DataScopeEnforcer
from libs.iam.data_scope_policy import (
    DataAction,
    DataResource,
    enforce_data_scope,
    require_permission_context,
    resolve_team_ids_for_context,
)

__all__ = [
    "DataAction",
    "DataResource",
    "DataScopeEnforcer",
    "enforce_data_scope",
    "require_permission_context",
    "resolve_team_ids_for_context",
]
