"""跨团队模型列表：凭据筛选下拉读投影（非 domain 不变量；自 repository 行映射）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True)
class TeamRegistryCredentialDisplay:
    """团队注册模型引用的凭据（列表筛选下拉，不做 reveal 过滤）。"""

    id: uuid.UUID
    name: str
    provider: str
    tenant_id: uuid.UUID


__all__ = ["TeamRegistryCredentialDisplay"]
