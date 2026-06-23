"""团队 slug 生成规则（纯函数，无 IO）。

slug 既是展示标识，也是跨团队 vkey 的模型前缀 ``<slug>/<model>``（派发与
``/v1/models`` 列表 id 对称）。个人团队按 owner 唯一（每用户至多一个），slug 无需
嵌入完整 UUID——用短 hex 让前缀更短、可读。
"""

from __future__ import annotations

import uuid

PERSONAL_SLUG_PREFIX = "personal-"

# 个人团队 slug 取 user_id 的前 8 位 hex（与共享团队 ``team-<hex8>`` 长度对齐）。
_PERSONAL_SLUG_HEX_LEN = 8


def personal_team_slug(user_id: uuid.UUID) -> str:
    """个人团队 slug：``personal-<user_id 前 8 位 hex>``（如 ``personal-877ae63a``）。"""
    return f"{PERSONAL_SLUG_PREFIX}{user_id.hex[:_PERSONAL_SLUG_HEX_LEN]}"


__all__ = ["PERSONAL_SLUG_PREFIX", "personal_team_slug"]
