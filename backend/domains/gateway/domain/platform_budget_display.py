"""Platform 预算展示读纯规则（日志兜底资格）。"""

from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class PlatformBudgetLogScope:
    """日志窗口聚合所需的 platform 预算维度（展示读专用）。"""

    target_kind: str
    target_id: uuid.UUID | None
    model_name: str | None
    credential_id: uuid.UUID | None
    tenant_id: uuid.UUID | None


def platform_log_fallback_supported(scope: PlatformBudgetLogScope) -> bool:
    """``system`` 维度无稳定日志归因，仅信任 bucket。"""
    return scope.target_kind != "system"


__all__ = [
    "PlatformBudgetLogScope",
    "platform_log_fallback_supported",
]
