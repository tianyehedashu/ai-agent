"""管理面团队上下文（JWT + X-Team-Id 解析结果）。"""

from __future__ import annotations

from dataclasses import dataclass
import uuid


@dataclass(frozen=True)
class ManagementTeamContext:
    """管理面 `/api/v1/gateway/*` 等路由解析后的团队上下文。"""

    team_id: uuid.UUID
    team_kind: str
    team_role: str
    user_id: uuid.UUID
    is_platform_admin: bool


__all__ = ["ManagementTeamContext"]
