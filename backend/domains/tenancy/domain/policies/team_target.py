"""团队 ID 解析（纯函数）：路径参数优先于 X-Team-Id 头。"""

from __future__ import annotations

from contextlib import suppress
import uuid


def parse_team_id_header(
    path_team_id: str | None,
    x_team_id: str | None,
) -> uuid.UUID | None:
    """解析显式团队 ID；非法 UUID 视为未指定。"""
    if path_team_id:
        with suppress(ValueError):
            return uuid.UUID(path_team_id)
    if x_team_id:
        trimmed = x_team_id.strip()
        if trimmed:
            with suppress(ValueError):
                return uuid.UUID(trimmed)
    return None


__all__ = ["parse_team_id_header"]
