"""模型注册表 ``registry_scope`` 读侧过滤策略（纯函数）。"""

from __future__ import annotations

from typing import Literal

RegistryScope = Literal["team", "system", "callable", "requestable"]


def exclude_user_scope_credentials_for_registry(registry_scope: RegistryScope) -> bool:
    """``registry_scope=team`` 时排除 ``scope=user``（BYOK）凭据绑定的租户注册行。

    personal team 工作区与共享团队共用 ``tenant_id`` 轴；BYOK 物理上落在 personal
    tenant 但不应出现在「团队注册表」Tab。``callable`` / ``requestable`` / ``/v1/models``
    仍须包含 BYOK 别名。
    """
    return registry_scope == "team"


__all__ = ["RegistryScope", "exclude_user_scope_credentials_for_registry"]
