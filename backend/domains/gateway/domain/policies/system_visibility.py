"""系统模型可见性过滤（纯函数，不依赖 ORM / Session）。"""

from __future__ import annotations

from dataclasses import dataclass
import uuid  # noqa: TC003

from domains.gateway.domain.visibility import (
    Visibility,
    effective_visibility,
    is_subject_granted,
)


@dataclass(frozen=True, slots=True)
class SystemModelVisibilitySnapshot:
    """单条 system 模型在可见性判定上的最小快照。"""

    model_id: uuid.UUID
    credential_id: uuid.UUID
    model_visibility: str
    credential_visibility: str


def snapshots_need_grant_lookup(
    snapshots: list[SystemModelVisibilitySnapshot],
) -> bool:
    """是否存在至少一条 restricted（含 inherit→restricted）行。"""
    for snap in snapshots:
        if (
            effective_visibility(snap.model_visibility, snap.credential_visibility)
            == Visibility.RESTRICTED
        ):
            return True
    return False


def visible_system_model_ids(
    snapshots: list[SystemModelVisibilitySnapshot],
    granted_keys: set[tuple[str, uuid.UUID]],
) -> set[uuid.UUID]:
    """返回当前主体可见的 system 模型 id 集合。"""
    visible: set[uuid.UUID] = set()
    for snap in snapshots:
        eff = effective_visibility(snap.model_visibility, snap.credential_visibility)
        if eff == Visibility.PUBLIC:
            visible.add(snap.model_id)
            continue
        if is_subject_granted(
            subject_kind="model",
            subject_id=snap.model_id,
            credential_id=snap.credential_id,
            granted_subject_keys=granted_keys,
        ):
            visible.add(snap.model_id)
    return visible


__all__ = [
    "SystemModelVisibilitySnapshot",
    "snapshots_need_grant_lookup",
    "visible_system_model_ids",
]
