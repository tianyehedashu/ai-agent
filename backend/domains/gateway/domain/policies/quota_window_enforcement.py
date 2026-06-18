"""配额行「启用停用 + 起止时间」执法判定（纯函数）。

平台预算行、上游/下游窗口配额共用同一规则：停用或不在有效期内的行
不参与热路径执法（既不预扣也不阻断），等价于该行不存在。``valid_from`` /
``valid_until`` 为 ``None`` 表示该侧不限。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


def is_quota_row_enforceable(
    *,
    enabled: bool,
    valid_from: datetime | None,
    valid_until: datetime | None,
    now: datetime,
) -> bool:
    """该配额行此刻是否应纳入执法。

    - ``enabled=False`` → 跳过；
    - ``now < valid_from`` → 未生效，跳过；
    - ``now >= valid_until`` → 已失效，跳过；
    - 起止时间任一为 ``None`` 表示该侧不限。
    """
    if not enabled:
        return False
    if valid_from is not None and now < valid_from:
        return False
    return valid_until is None or now < valid_until


__all__ = ["is_quota_row_enforceable"]
