"""个人资源 grant 可见性纯规则（不依赖 ORM / Session）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import uuid

from .visibility import is_subject_granted

ResourceGrantSubjectKind = Literal["credential", "model"]


@dataclass(frozen=True, slots=True)
class GrantedModelSnapshot:
    """授权模型可见性判定的最小快照。"""

    model_id: uuid.UUID
    credential_id: uuid.UUID
    owner_user_id: uuid.UUID
    personal_team_id: uuid.UUID


def visible_granted_model_ids(
    snapshots: list[GrantedModelSnapshot],
    granted_keys: set[tuple[str, uuid.UUID]],
) -> set[uuid.UUID]:
    """返回当前团队可见的授权个人模型 id 集合。"""
    visible: set[uuid.UUID] = set()
    for snap in snapshots:
        if is_subject_granted(
            subject_kind="model",
            subject_id=snap.model_id,
            credential_id=snap.credential_id,
            granted_subject_keys=granted_keys,
        ):
            visible.add(snap.model_id)
    return visible


def credential_granted_to_team(
    credential_id: uuid.UUID,
    granted_keys: set[tuple[str, uuid.UUID]],
) -> bool:
    return ("credential", credential_id) in granted_keys


__all__ = [
    "GrantedModelSnapshot",
    "ResourceGrantSubjectKind",
    "credential_granted_to_team",
    "visible_granted_model_ids",
]
