"""团队展示名纯函数（与前端 gatewayTeamDisplayLabel 对齐）。"""

from __future__ import annotations

import uuid


def format_team_display_label(
    *,
    kind: str,
    name: str,
    owner_user_id: uuid.UUID,
    viewer_user_id: uuid.UUID | None = None,
    owner_hint: str | None = None,
) -> str:
    """personal 且非本人视角 →「个人 · {owner}」；本人 personal →「个人工作区」；shared → name。"""
    if kind == "personal":
        if viewer_user_id is not None and owner_user_id != viewer_user_id:
            hint = owner_hint or f"{str(owner_user_id)[:8]}…"
            return f"个人 · {hint}"
        return "个人工作区"
    return name


__all__ = ["format_team_display_label"]
