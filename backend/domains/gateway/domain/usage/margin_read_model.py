"""Gateway 管理读模型：套餐毛利聚合维度与展示标签。"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

MarginGroupBy = Literal["credential", "model", "team"]

_LABEL_UNLINKED_CREDENTIAL = "未关联凭据"
_LABEL_UNKNOWN_MODEL = "未知模型"
_LABEL_UNLINKED_TEAM = "未关联团队"

_MARGIN_GROUP_COLUMN: dict[MarginGroupBy, str] = {
    "credential": "凭据",
    "model": "模型",
    "team": "团队",
}


def margin_group_column_label(group_by: MarginGroupBy) -> str:
    return _MARGIN_GROUP_COLUMN[group_by]


def resolve_margin_group_label(
    group_by: MarginGroupBy,
    group_key: object,
    *,
    credential_names: dict[UUID, str] | None = None,
    credential_name_snapshot: str | None = None,
    team_names: dict[UUID, str] | None = None,
) -> tuple[str, str]:
    """将聚合分组键解析为 (group_key, 展示标签)。"""
    if group_by == "credential":
        if group_key is None:
            return "", _LABEL_UNLINKED_CREDENTIAL
        cred_id = group_key if isinstance(group_key, UUID) else UUID(str(group_key))
        key = str(cred_id)
        names = credential_names or {}
        if cred_id in names:
            return key, names[cred_id]
        snap = (credential_name_snapshot or "").strip()
        if snap:
            return key, snap[:100]
        return key, f"{key[:8]}…"

    if group_by == "model":
        if group_key is None or str(group_key).strip() == "":
            return "", _LABEL_UNKNOWN_MODEL
        model = str(group_key).strip()
        return model, model

    if group_key is None:
        return "", _LABEL_UNLINKED_TEAM
    team_id = group_key if isinstance(group_key, UUID) else UUID(str(group_key))
    key = str(team_id)
    names = team_names or {}
    if team_id in names:
        return key, names[team_id]
    return key, f"{key[:8]}…"


__all__ = [
    "MarginGroupBy",
    "margin_group_column_label",
    "resolve_margin_group_label",
]
